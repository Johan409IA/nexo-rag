from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Fragmento:
    """Unidad recuperable por el RAG.

    El embedding no forma parte del modelo de dominio: se persiste en la base y
    viaja en una lista paralela hacia el ``VectorStore``.
    """

    id: int | None
    documento_id: int | None
    texto: str
    pagina: int
    chunk_index: int

    def __post_init__(self) -> None:
        if self.pagina < 1:
            raise ValueError("pagina debe ser >= 1")
        if self.chunk_index < 0:
            raise ValueError("chunk_index debe ser >= 0")
