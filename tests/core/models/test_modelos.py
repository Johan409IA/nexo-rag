from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime

import pytest

from core.models import Documento, Fragmento, Fuente, RespuestaRAG, ResultadoBusqueda

HASH_VALIDO = "a" * 64


def test_documento_valido() -> None:
    documento = Documento(
        id=None,
        nombre="clase-04.pdf",
        curso="Diseño de Software",
        hash_sha256=HASH_VALIDO,
        fecha_ingesta=datetime(2026, 10, 7, tzinfo=UTC),
    )
    assert documento.nombre == "clase-04.pdf"
    assert documento.fecha_ingesta is not None


@pytest.mark.parametrize("nombre", ["", "   "])
def test_documento_rechaza_nombre_vacio(nombre: str) -> None:
    with pytest.raises(ValueError, match="nombre"):
        Documento(id=None, nombre=nombre, curso="Diseño de Software", hash_sha256=HASH_VALIDO)


@pytest.mark.parametrize("curso", ["", "   "])
def test_documento_rechaza_curso_vacio(curso: str) -> None:
    with pytest.raises(ValueError, match="curso"):
        Documento(id=None, nombre="clase-04.pdf", curso=curso, hash_sha256=HASH_VALIDO)


@pytest.mark.parametrize("hash_sha256", ["", "A" * 64, "a" * 63, "a" * 65, "z" * 64])
def test_documento_rechaza_hash_invalido(hash_sha256: str) -> None:
    with pytest.raises(ValueError, match="hash_sha256"):
        Documento(id=None, nombre="clase-04.pdf", curso="curso", hash_sha256=hash_sha256)


def test_modelos_son_inmutables() -> None:
    documento = Documento(id=None, nombre="x.pdf", curso="curso", hash_sha256=HASH_VALIDO)
    with pytest.raises(FrozenInstanceError):
        documento.nombre = "otro.pdf"


def test_fragmento_valido() -> None:
    fragmento = Fragmento(id=None, documento_id=None, texto="texto", pagina=1, chunk_index=0)
    assert fragmento.chunk_index == 0


def test_fragmento_no_contiene_embedding() -> None:
    assert "embedding" not in {campo.name for campo in fields(Fragmento)}


def test_fragmento_rechaza_pagina_invalida() -> None:
    with pytest.raises(ValueError, match="pagina"):
        Fragmento(id=None, documento_id=None, texto="texto", pagina=0, chunk_index=0)


def test_fragmento_rechaza_chunk_index_negativo() -> None:
    with pytest.raises(ValueError, match="chunk_index"):
        Fragmento(id=None, documento_id=None, texto="texto", pagina=1, chunk_index=-1)


def test_resultado_busqueda_valido() -> None:
    resultado = ResultadoBusqueda(
        texto="texto", documento="x.pdf", curso="curso", pagina=3, score=0.75
    )
    assert resultado.score == 0.75


def test_resultado_busqueda_rechaza_pagina_invalida() -> None:
    with pytest.raises(ValueError, match="pagina"):
        ResultadoBusqueda(texto="texto", documento="x.pdf", curso="curso", pagina=0, score=0.75)


def test_respuesta_rag_con_fuentes() -> None:
    fuente = Fuente(documento="x.pdf", curso="curso", pagina=2)
    respuesta = RespuestaRAG(respuesta="ok", fuentes=[fuente])
    assert respuesta.fuentes == [fuente]
