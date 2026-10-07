from core.models import ResultadoBusqueda
from core.ports.embedder import Embedder
from core.ports.vector_store import VectorStore

K_POR_DEFECTO = 4


class BuscarFragmentos:
    """Recupera los fragmentos más similares a una consulta."""

    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self.embedder = embedder
        self.store = store

    def ejecutar(
        self,
        consulta: str,
        k: int = K_POR_DEFECTO,
        curso: str | None = None,
    ) -> list[ResultadoBusqueda]:
        if not consulta.strip():
            raise ValueError("consulta no puede estar vacía")
        if k < 1:
            raise ValueError("k debe ser >= 1")

        vector = self.embedder.embed_consulta(consulta)
        return self.store.buscar(vector, k=k, curso=curso)
