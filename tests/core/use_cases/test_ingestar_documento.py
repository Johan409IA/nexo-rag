import pytest

from core.models import Documento
from core.use_cases.ingestar_documento import (
    DocumentoDuplicadoError,
    IngestarDocumento,
    ResultadoIngesta,
)
from tests.fakes import FakeChunker, FakeDocumentLoader, FakeEmbedder, InMemoryVectorStore

HASH_VALIDO = "a" * 64


def _caso() -> IngestarDocumento:
    return IngestarDocumento(
        loader=FakeDocumentLoader(),
        chunker=FakeChunker(),
        embedder=FakeEmbedder(),
        store=InMemoryVectorStore(),
    )


def test_se_construye_con_fakes() -> None:
    caso = _caso()

    assert caso.MIN_CARACTERES_PAGINA == 50


def test_ejecutar_sigue_siendo_esqueleto() -> None:
    caso = _caso()

    with pytest.raises(NotImplementedError, match="Fase 1"):
        caso.ejecutar("ruta.pdf", "curso")


def test_tipos_del_resultado_y_el_error() -> None:
    documento = Documento(id=None, nombre="x.pdf", curso="curso", hash_sha256=HASH_VALIDO)

    resultado = ResultadoIngesta(documento=documento, paginas_omitidas=[1, 3])

    assert resultado.paginas_omitidas == [1, 3]
    assert issubclass(DocumentoDuplicadoError, Exception)
