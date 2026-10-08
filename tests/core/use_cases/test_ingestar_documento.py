import hashlib

import pytest

from core.models import Documento
from core.use_cases.ingestar_documento import (
    DocumentoDuplicadoError,
    IngestarDocumento,
    ResultadoIngesta,
)
from tests.fakes import (
    FakeChunker,
    FakeDocumentLoader,
    FakeEmbedder,
    InMemoryVectorStore,
)

HASH_VALIDO = "a" * 64
TEXTO_LARGO = "cohesión y acoplamiento en el diseño de software" * 3


def _archivo(tmp_path, nombre: str = "apuntes.pdf", contenido: bytes = b"contenido") -> str:
    ruta = tmp_path / nombre
    ruta.write_bytes(contenido)
    return str(ruta)


def _caso(paginas=None, store=None, embedder=None) -> tuple[IngestarDocumento, InMemoryVectorStore]:
    store = store if store is not None else InMemoryVectorStore()
    caso = IngestarDocumento(
        loader=FakeDocumentLoader(paginas=paginas),
        chunker=FakeChunker(),
        embedder=embedder if embedder is not None else FakeEmbedder(),
        store=store,
    )
    return caso, store


def test_se_construye_con_fakes() -> None:
    caso, _ = _caso()

    assert caso.MIN_CARACTERES_PAGINA == 50


def test_tipos_del_resultado_y_el_error() -> None:
    documento = Documento(id=None, nombre="x.pdf", curso="curso", hash_sha256=HASH_VALIDO)

    resultado = ResultadoIngesta(documento=documento, paginas_omitidas=[1, 3])

    assert resultado.paginas_omitidas == [1, 3]
    assert issubclass(DocumentoDuplicadoError, Exception)


def test_ejecutar_guarda_documento_y_fragmentos(tmp_path) -> None:
    ruta = _archivo(tmp_path, contenido=b"pdf real")
    caso, store = _caso(paginas=[(1, TEXTO_LARGO)])

    resultado = caso.ejecutar(ruta, "curso")

    assert resultado.documento.nombre == "apuntes.pdf"
    assert resultado.documento.curso == "curso"
    assert resultado.documento.hash_sha256 == hashlib.sha256(b"pdf real").hexdigest()
    assert resultado.paginas_omitidas == []
    assert store.existe_hash(resultado.documento.hash_sha256) is True
    assert [r.pagina for r in store.buscar([1.0] + [0.0] * 767, k=10)] == [1]


def test_ejecutar_omite_paginas_cortas_y_las_reporta(tmp_path) -> None:
    ruta = _archivo(tmp_path)
    embedder = FakeEmbedder()
    caso, store = _caso(
        paginas=[(1, TEXTO_LARGO), (2, "  corta  "), (3, "   "), (4, "otro texto largo " * 5)],
        embedder=embedder,
    )

    resultado = caso.ejecutar(ruta, "curso")

    assert resultado.paginas_omitidas == [2, 3]
    assert embedder.llamadas_documentos == [[TEXTO_LARGO, ("otro texto largo " * 5).strip()]]


def test_ejecutar_pasa_textos_strip_al_embedder(tmp_path) -> None:
    ruta = _archivo(tmp_path)
    embedder = FakeEmbedder()
    caso, _ = _caso(paginas=[(1, f"  {TEXTO_LARGO}  ")], embedder=embedder)

    caso.ejecutar(ruta, "curso")

    assert embedder.llamadas_documentos == [[TEXTO_LARGO]]


def test_ejecutar_con_todas_las_paginas_omitidas_guarda_sin_fragmentos(tmp_path) -> None:
    ruta = _archivo(tmp_path)
    caso, store = _caso(paginas=[(1, "corta"), (2, "también corta")])

    resultado = caso.ejecutar(ruta, "curso")

    assert resultado.paginas_omitidas == [1, 2]
    assert store.existe_hash(resultado.documento.hash_sha256) is True
    assert store.buscar([1.0] + [0.0] * 767, k=10) == []


def test_ejecutar_rechaza_duplicado(tmp_path) -> None:
    ruta = _archivo(tmp_path)
    caso, store = _caso(paginas=[(1, TEXTO_LARGO)])
    caso.ejecutar(ruta, "curso")

    with pytest.raises(DocumentoDuplicadoError):
        caso.ejecutar(ruta, "otro curso")

    resultados = store.buscar([1.0] + [0.0] * 767, k=10)
    assert [resultado.curso for resultado in resultados] == ["curso"]


def test_ejecutar_con_ruta_inexistente_falla_al_calcular_hash(tmp_path) -> None:
    caso, _ = _caso(paginas=[(1, TEXTO_LARGO)])

    with pytest.raises(FileNotFoundError):
        caso.ejecutar(str(tmp_path / "no-existe.pdf"), "curso")
