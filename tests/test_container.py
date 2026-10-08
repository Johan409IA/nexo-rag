import importlib

import pytest

import container
from container import (
    cargar_configuracion,
    construir_buscar_fragmentos,
    construir_chunker,
    construir_embedder_gemini,
    construir_ingestar,
    construir_loader_pdf,
    construir_preguntar,
    construir_vector_store,
)
from core.use_cases.buscar_fragmentos import BuscarFragmentos
from core.use_cases.ingestar_documento import IngestarDocumento
from core.use_cases.preguntar import Preguntar
from tests.fakes import FakeChunker, FakeDocumentLoader, FakeEmbedder, FakeLLM, InMemoryVectorStore


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_LLM_MODEL", raising=False)


def test_configuracion_sin_variables_de_integracion() -> None:
    configuracion = cargar_configuracion()

    assert configuracion.database_url is None
    assert configuracion.gemini_api_key is None
    assert configuracion.gemini_llm_model == "gemini-2.5-flash"


def test_parsea_variables_de_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://ejemplo")
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-ejemplo")
    monkeypatch.setenv("GEMINI_LLM_MODEL", "gemini-2.5-flash")

    configuracion = cargar_configuracion()

    assert configuracion.database_url == "postgresql://ejemplo"
    assert configuracion.gemini_api_key == "clave-de-ejemplo"
    assert configuracion.gemini_llm_model == "gemini-2.5-flash"


def test_repr_no_muestra_secretos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://secreto-db")
    monkeypatch.setenv("GEMINI_API_KEY", "secreto-clave")

    texto = repr(cargar_configuracion())

    assert "secreto-db" not in texto
    assert "secreto-clave" not in texto
    assert "gemini-2.5-flash" in texto


def test_fabricas_conectan_puertos_fakes_a_casos_de_uso() -> None:
    embedder = FakeEmbedder()
    store = InMemoryVectorStore()
    buscar = construir_buscar_fragmentos(embedder=embedder, store=store)
    preguntar = construir_preguntar(buscar=buscar, llm=FakeLLM())
    ingestar = construir_ingestar(
        loader=FakeDocumentLoader(), chunker=FakeChunker(), embedder=embedder, store=store
    )

    assert isinstance(buscar, BuscarFragmentos)
    assert isinstance(preguntar, Preguntar)
    assert isinstance(ingestar, IngestarDocumento)
    assert buscar.ejecutar("cohesión") == []


def test_importar_container_no_produce_efectos() -> None:
    importlib.reload(container)

    assert callable(container.cargar_configuracion)
    assert container.Configuracion().gemini_llm_model == "gemini-2.5-flash"


def test_fabricas_de_adaptadores_construyen_los_adaptadores_reales() -> None:
    from adapters.ai.gemini_embedder import GeminiEmbedder
    from adapters.chunking.page_chunker import PageChunker
    from adapters.database.pgvector_store import PgVectorStore
    from adapters.pdf.pymupdf_loader import PyMuPDFLoader

    loader = construir_loader_pdf()
    chunker = construir_chunker()
    embedder = construir_embedder_gemini("clave-de-ejemplo")
    store = construir_vector_store("postgresql://ejemplo")

    assert isinstance(loader, PyMuPDFLoader)
    assert isinstance(chunker, PageChunker)
    assert isinstance(embedder, GeminiEmbedder)
    assert isinstance(store, PgVectorStore)
