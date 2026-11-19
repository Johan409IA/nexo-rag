import time

from google import genai
from google.genai import errors

MODELO_LLM = "gemini-3.5-flash-lite"
ESPERA_REINTENTOS = (2.0, 4.0, 8.0, 16.0, 32.0)


class GeminiLLM:
    """LLM generativo de Gemini para responder con el contexto recuperado.

    Usa ``MODELO_LLM`` salvo que se indique otro modelo. Ante errores
    transitorios (429 de cuota y 503 de alta demanda) reintenta con esperas
    crecientes y, agotados los reintentos, propaga el error. Una respuesta
    sin texto se considera un error del proveedor y se convierte en
    ``ValueError``.
    """

    def __init__(self, api_key: str, modelo: str | None = None) -> None:
        self.client = genai.Client(api_key=api_key)
        self.modelo = modelo or MODELO_LLM

    def responder(self, prompt: str) -> str:
        intento = 0
        while True:
            try:
                resultado = self.client.models.generate_content(model=self.modelo, contents=prompt)
            except errors.APIError as error:
                if error.code not in (429, 503) or intento >= len(ESPERA_REINTENTOS):
                    raise
                time.sleep(ESPERA_REINTENTOS[intento])
                intento += 1
                continue

            texto = resultado.text
            if not texto:
                raise ValueError("Gemini no devolvió texto")

            return texto
