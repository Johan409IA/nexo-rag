from typing import Protocol


class Embedder(Protocol):
    """Genera embeddings de 768 dimensiones para documentos y consultas.

    ``embed_documentos`` y ``embed_consulta`` devuelven la misma cantidad de
    vectores que elementos recibidos y en el mismo orden (``[]`` → ``[]``).
    Cada vector tiene dimensión fija 768. El formato interno que requiera el
    modelo (prefijos de documento/consulta) se aplica dentro del adaptador.
    """

    def embed_documentos(self, textos: list[str]) -> list[list[float]]: ...

    def embed_consulta(self, consulta: str) -> list[float]: ...
