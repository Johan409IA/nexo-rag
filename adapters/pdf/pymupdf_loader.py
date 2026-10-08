from pathlib import Path

import pymupdf


class PyMuPDFLoader:
    """Extrae el texto de cada página de un PDF con PyMuPDF.

    Devuelve pares ``(pagina, texto)`` con la numeración desde 1, el texto ya
    ``strip()``eado y las páginas vacías incluidas; el filtrado corresponde a
    ``IngestarDocumento``. Si la ruta no existe lanza ``FileNotFoundError``
    (PyMuPDF define una excepción propia con ese nombre, distinta de la de la
    biblioteca estándar).
    """

    @staticmethod
    def leer(ruta: str) -> list[tuple[int, str]]:
        if not Path(ruta).is_file():
            raise FileNotFoundError(ruta)

        paginas = []

        with pymupdf.open(ruta) as doc:
            for numero, pagina in enumerate(doc, start=1):
                texto = pagina.get_text().strip()
                paginas.append((numero, texto))

        return paginas
