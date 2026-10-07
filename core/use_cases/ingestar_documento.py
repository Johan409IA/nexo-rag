from dataclasses import dataclass

from core.models import Documento
from core.ports.chunker import Chunker
from core.ports.document_loader import DocumentLoader
from core.ports.embedder import Embedder
from core.ports.vector_store import VectorStore


class DocumentoDuplicadoError(Exception):
    """El hash del documento ya existe en el almacén."""


@dataclass(frozen=True, slots=True)
class ResultadoIngesta:
    """Documento ingestado junto con los números de página omitidos."""

    documento: Documento
    paginas_omitidas: list[int]


class IngestarDocumento:
    """Convierte un PDF en fragmentos vectorizados.

    Esqueleto durante la Fase 0: el flujo completo (hash SHA-256, detección de
    duplicados, filtrado de páginas de menos de ``MIN_CARACTERES_PAGINA``
    caracteres, chunking y persistencia) se implementa en la Fase 1.
    """

    MIN_CARACTERES_PAGINA = 50

    def __init__(
        self,
        loader: DocumentLoader,
        chunker: Chunker,
        embedder: Embedder,
        store: VectorStore,
    ) -> None:
        self.loader = loader
        self.chunker = chunker
        self.embedder = embedder
        self.store = store

    def ejecutar(self, ruta: str, curso: str) -> ResultadoIngesta:
        raise NotImplementedError("Fase 1")
