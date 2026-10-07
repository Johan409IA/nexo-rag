import os
from dataclasses import dataclass, field

from core.ports.chunker import Chunker
from core.ports.document_loader import DocumentLoader
from core.ports.embedder import Embedder
from core.ports.llm import LLM
from core.ports.vector_store import VectorStore
from core.use_cases.buscar_fragmentos import BuscarFragmentos
from core.use_cases.ingestar_documento import IngestarDocumento
from core.use_cases.preguntar import Preguntar

GEMINI_LLM_MODEL_POR_DEFECTO = "gemini-2.5-flash"


@dataclass(frozen=True, slots=True)
class Configuracion:
    """Configuración de integración del backend y el CLI.

    Los valores de integración son opcionales en la Fase 0 y solo se validan al
    construir los adaptadores reales. Los campos secretos no aparecen en
    ``repr``.
    """

    gemini_llm_model: str | None = GEMINI_LLM_MODEL_POR_DEFECTO
    database_url: str | None = field(default=None, repr=False)
    gemini_api_key: str | None = field(default=None, repr=False)


def cargar_configuracion() -> Configuracion:
    """Lee las variables de entorno del proceso con biblioteca estándar.

    No busca `.env` ni inicia integraciones: solo se ejecuta al invocarla.
    """
    return Configuracion(
        database_url=os.environ.get("DATABASE_URL") or None,
        gemini_api_key=os.environ.get("GEMINI_API_KEY") or None,
        gemini_llm_model=os.environ.get("GEMINI_LLM_MODEL") or GEMINI_LLM_MODEL_POR_DEFECTO,
    )


def construir_buscar_fragmentos(embedder: Embedder, store: VectorStore) -> BuscarFragmentos:
    """Construye ``BuscarFragmentos`` a partir de puertos ya instanciados."""
    return BuscarFragmentos(embedder=embedder, store=store)


def construir_preguntar(buscar: BuscarFragmentos, llm: LLM) -> Preguntar:
    """Construye ``Preguntar`` a partir de su caso de búsqueda y un puerto ``LLM``."""
    return Preguntar(buscar=buscar, llm=llm)


def construir_ingestar(
    loader: DocumentLoader,
    chunker: Chunker,
    embedder: Embedder,
    store: VectorStore,
) -> IngestarDocumento:
    """Construye ``IngestarDocumento``; su flujo completo se implementa en la Fase 1."""
    return IngestarDocumento(loader=loader, chunker=chunker, embedder=embedder, store=store)
