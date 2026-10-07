from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResultadoBusqueda:
    """Fragmento recuperado junto con su procedencia.

    ``score`` es la similitud coseno (1 - distancia coseno): un valor mayor
    indica mayor similitud con la consulta. No se usa como threshold en el
    baseline del MVP.
    """

    texto: str
    documento: str
    curso: str
    pagina: int
    score: float

    def __post_init__(self) -> None:
        if self.pagina < 1:
            raise ValueError("pagina debe ser >= 1")
