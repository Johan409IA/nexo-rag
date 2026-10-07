from typing import Protocol


class DocumentLoader(Protocol):
    """Extrae las páginas de un documento.

    Devuelve pares ``(pagina, texto)`` numerados desde 1 y en orden, con el
    texto ya pasado por ``strip()``. Incluye las páginas vacías: el filtrado por
    longitud es responsabilidad del caso de uso de ingesta. Lanza
    ``FileNotFoundError`` si la ruta no existe.
    """

    def leer(self, ruta: str) -> list[tuple[int, str]]: ...
