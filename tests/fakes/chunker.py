from core.models import Fragmento


class FakeChunker:
    """``Chunker`` que convierte cada página recibida en un fragmento.

    No filtra páginas: respeta el contrato según el cual recibe páginas ya
    validadas por el caso de uso de ingesta.
    """

    def __init__(self) -> None:
        self.llamadas: list[list[tuple[int, str]]] = []

    def crear_fragmentos(self, paginas: list[tuple[int, str]]) -> list[Fragmento]:
        self.llamadas.append(list(paginas))
        return [
            Fragmento(
                id=None,
                documento_id=None,
                texto=texto,
                pagina=pagina,
                chunk_index=0,
            )
            for pagina, texto in paginas
        ]
