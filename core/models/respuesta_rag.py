from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Fuente:
    """Procedencia de un fragmento usado para construir la respuesta."""

    documento: str
    curso: str
    pagina: int


@dataclass(frozen=True, slots=True)
class RespuestaRAG:
    """Respuesta estructurada del RAG: texto y fuentes."""

    respuesta: str
    fuentes: list[Fuente]
