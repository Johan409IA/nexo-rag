from collections.abc import Sequence

import pytest
from psycopg.errors import UniqueViolation

import adapters.database.pgvector_store as modulo_store
from adapters.database.pgvector_store import PgVectorStore
from core.models import Documento, Fragmento
from core.use_cases.ingestar_documento import DocumentoDuplicadoError


class _CursorFake:
    def __init__(
        self,
        fila: tuple[object, ...] | None = None,
        filas: list[tuple[object, ...]] | None = None,
    ) -> None:
        self._fila = fila
        self._filas = filas or []

    def fetchone(self) -> tuple[object, ...] | None:
        return self._fila

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._filas


class _TransaccionFake:
    def __init__(self, conexion) -> None:
        self.conexion = conexion

    def __enter__(self):
        self.conexion.transacciones += 1
        return self

    def __exit__(self, tipo_error, error, traceback):
        if tipo_error is not None:
            self.conexion.rollback()
        else:
            self.conexion.commit()
        return False


class _ConexionFake:
    def __init__(self, filas=None, fallar_fragmento=False, unique_violation=False) -> None:
        self.filas = filas or []
        self.fallar_fragmento = fallar_fragmento
        self.unique_violation = unique_violation
        self.documento_sin_fila = False
        self.consultas: list[tuple[str, Sequence[object] | None]] = []
        self.transacciones = 0
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def execute(
        self,
        consulta: str,
        parametros: Sequence[object] | None = None,
    ) -> _CursorFake:
        self.consultas.append((consulta, parametros))
        if consulta.startswith("SELECT 1 FROM public.documentos"):
            return _CursorFake(fila=(1,) if self.filas else None)
        if "INSERT INTO public.documentos" in consulta:
            if self.unique_violation:
                raise UniqueViolation("duplicado")
            if self.documento_sin_fila:
                return _CursorFake()
            return _CursorFake(fila=(123,))
        if "INSERT INTO public.fragmentos" in consulta and self.fallar_fragmento:
            raise RuntimeError("falló la inserción del fragmento")
        if consulta.startswith("SELECT f.texto"):
            return _CursorFake(filas=self.filas)
        return _CursorFake()

    def transaction(self):
        return _TransaccionFake(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _patch_conexion(monkeypatch, conexion) -> None:
    monkeypatch.setattr(modulo_store, "conectar", lambda _database_url: conexion)
    monkeypatch.setattr(modulo_store, "register_vector", lambda _conn: None)


def test_existe_hash_consulta_documentos(monkeypatch) -> None:
    conexion = _ConexionFake()
    _patch_conexion(monkeypatch, conexion)

    assert PgVectorStore("postgresql://prueba").existe_hash("a" * 64) is False

    assert "WHERE hash_sha256 = %s" in conexion.consultas[-1][0]
    assert conexion.closed


def test_guardar_inserta_documento_y_fragmento_en_una_transaccion(monkeypatch) -> None:
    conexion = _ConexionFake()
    _patch_conexion(monkeypatch, conexion)
    documento = Documento(id=None, nombre="a.pdf", curso="curso", hash_sha256="a" * 64)
    fragmento = Fragmento(id=None, documento_id=None, texto="contenido", pagina=2, chunk_index=0)

    PgVectorStore("postgresql://prueba").guardar_documento_con_fragmentos(
        documento, [fragmento], [[0.1] * 768]
    )

    assert conexion.transacciones == 1
    assert conexion.commits == 3
    assert conexion.rollbacks == 0
    assert sum("INSERT INTO public.documentos" in sql for sql, _ in conexion.consultas) == 1
    assert sum("INSERT INTO public.fragmentos" in sql for sql, _ in conexion.consultas) == 1
    assert conexion.closed


def test_guardar_valida_longitud_antes_de_conectar(monkeypatch) -> None:
    conectada = False

    def conectar_fake(_database_url):
        nonlocal conectada
        conectada = True
        return _ConexionFake()

    monkeypatch.setattr(modulo_store, "conectar", conectar_fake)
    store = PgVectorStore("postgresql://prueba")
    documento = Documento(id=None, nombre="a.pdf", curso="curso", hash_sha256="a" * 64)
    fragmento = Fragmento(id=None, documento_id=None, texto="contenido", pagina=1, chunk_index=0)

    with pytest.raises(ValueError, match="longitud"):
        store.guardar_documento_con_fragmentos(documento, [fragmento], [])

    assert conectada is False


def test_guardar_traduce_hash_unico_a_error_de_duplicado(monkeypatch) -> None:
    conexion = _ConexionFake(unique_violation=True)
    _patch_conexion(monkeypatch, conexion)
    documento = Documento(id=None, nombre="a.pdf", curso="curso", hash_sha256="a" * 64)

    with pytest.raises(DocumentoDuplicadoError):
        PgVectorStore("postgresql://prueba").guardar_documento_con_fragmentos(documento, [], [])

    assert conexion.rollbacks == 1
    assert conexion.closed


def test_insert_documento_falla_si_returning_no_devuelve_fila(monkeypatch) -> None:
    conexion = _ConexionFake()
    conexion.documento_sin_fila = True
    _patch_conexion(monkeypatch, conexion)
    documento = Documento(id=None, nombre="a.pdf", curso="curso", hash_sha256="a" * 64)

    with pytest.raises(RuntimeError, match="no devolvió el id"):
        PgVectorStore("postgresql://prueba").guardar_documento_con_fragmentos(documento, [], [])

    assert conexion.rollbacks == 1
    assert conexion.closed


def test_fallo_insertando_fragmentos_revierte_transaccion(monkeypatch) -> None:
    conexion = _ConexionFake(fallar_fragmento=True)
    _patch_conexion(monkeypatch, conexion)
    documento = Documento(id=None, nombre="a.pdf", curso="curso", hash_sha256="a" * 64)
    fragmento = Fragmento(id=None, documento_id=None, texto="contenido", pagina=1, chunk_index=0)

    with pytest.raises(RuntimeError, match="falló"):
        PgVectorStore("postgresql://prueba").guardar_documento_con_fragmentos(
            documento, [fragmento], [[0.1] * 768]
        )

    assert conexion.rollbacks == 1
    assert conexion.closed


def test_buscar_usa_distancia_coseno_filtro_y_mapea_resultados(monkeypatch) -> None:
    conexion = _ConexionFake(filas=[("texto", "doc.pdf", "curso", 3, 0.875)])
    _patch_conexion(monkeypatch, conexion)

    resultados = PgVectorStore("postgresql://prueba").buscar([0.1] * 768, k=7, curso="curso")

    consulta, parametros = conexion.consultas[-1]

    assert parametros is not None
    assert "extensions.<=>" in consulta
    assert "WHERE d.curso = %s" in consulta
    assert "LIMIT %s" in consulta
    assert parametros[1] == "curso"
    assert parametros[-1] == 7
    assert resultados[0].texto == "texto"
    assert resultados[0].documento == "doc.pdf"
    assert resultados[0].curso == "curso"
    assert resultados[0].pagina == 3
    assert resultados[0].score == 0.875
    assert conexion.closed
