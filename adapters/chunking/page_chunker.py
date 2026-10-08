from core.models import Fragmento


class PageChunker:
    """Convierte cada página recibida en un fragmento con ``chunk_index = 0``.

    No aplica filtros: el descarte de páginas con poco contenido lo hace
    ``IngestarDocumento`` antes de llamar a este chunker.
    """

    @staticmethod
    def crear_fragmentos(paginas: list[tuple[int, str]]) -> list[Fragmento]:
        return [
            Fragmento(id=None, documento_id=None, texto=texto, pagina=pagina, chunk_index=0)
            for pagina, texto in paginas
        ]
