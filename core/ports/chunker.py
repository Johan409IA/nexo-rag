from typing import Protocol

from core.models import Fragmento


class Chunker(Protocol):
    """Crea fragmentos a partir de páginas ya filtradas.

    Recibe únicamente las páginas que el caso de uso de ingesta validó y
    convierte cada una en un fragmento con ``chunk_index = 0``. No consulta ni
    modifica nada externo ni descarta páginas.
    """

    def crear_fragmentos(self, paginas: list[tuple[int, str]]) -> list[Fragmento]: ...
