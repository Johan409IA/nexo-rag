class FakeLLM:
    """``LLM`` con respuesta fija que registra los prompts recibidos."""

    def __init__(self, respuesta: str = "respuesta del fake") -> None:
        self.respuesta = respuesta
        self.prompts: list[str] = []

    def responder(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.respuesta
