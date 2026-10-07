class FakeDocumentLoader:
    """``DocumentLoader`` que devuelve las páginas con las que se construye."""

    def __init__(self, paginas: list[tuple[int, str]] | None = None) -> None:
        self.paginas = list(paginas or [])
        self.rutas: list[str] = []

    def leer(self, ruta: str) -> list[tuple[int, str]]:
        self.rutas.append(ruta)
        return list(self.paginas)
