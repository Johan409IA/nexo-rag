from typing import Protocol


class LLM(Protocol):
    """Genera la respuesta final a partir del contexto recuperado.

    Recibe el prompt completo y devuelve texto plano; el caso de uso decide cómo
    presentarlo y qué fuentes acompañan la respuesta.
    """

    def responder(self, prompt: str) -> str: ...
