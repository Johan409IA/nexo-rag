from typing import Protocol

from core.models import Documento, Fragmento, ResultadoBusqueda


class VectorStore(Protocol):
    """Guarda y recupera fragmentos vectorizados.

    ``guardar_documento_con_fragmentos`` es atómico: o se guarda el documento
    con todos sus fragmentos o no se guarda nada. Lanza ``ValueError`` si
    ``len(fragmentos) != len(embeddings)`` y ``DocumentoDuplicadoError``
    (definido en ``core.use_cases.ingestar_documento``) si el hash ya existe,
    como protección frente a la carrera con ``existe_hash``.

    ``buscar`` devuelve como máximo ``k`` resultados ordenados por ``score``
    descendente; ``curso`` se compara por igualdad exacta.
    """

    def existe_hash(self, hash_sha256: str) -> bool: ...

    def guardar_documento_con_fragmentos(
        self,
        documento: Documento,
        fragmentos: list[Fragmento],
        embeddings: list[list[float]],
    ) -> None: ...

    def buscar(
        self,
        embedding: list[float],
        k: int = 4,
        curso: str | None = None,
    ) -> list[ResultadoBusqueda]: ...
