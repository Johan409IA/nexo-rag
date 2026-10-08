import time

from google import genai
from google.genai import errors, types

MODELO_EMBEDDINGS = "gemini-embedding-2"
TAMANO_LOTE = 50
ESPERA_REINTENTOS = (2.0, 4.0, 8.0)


class GeminiEmbedder:
    """Embedder de ``gemini-embedding-2`` con vectores de 768 dimensiones.

    Aplica prefijos distintos para documentos y consultas y procesa los textos
    por lotes de ``TAMANO_LOTE``. Ante errores de cuota (429) reintenta con
    esperas crecientes y, agotados los reintentos, propaga el error.
    """

    def __init__(self, api_key: str, dimensiones: int = 768) -> None:
        self.client = genai.Client(api_key=api_key)
        self.modelo = MODELO_EMBEDDINGS
        self.dimensiones = dimensiones

    def embed_documentos(self, textos: list[str]) -> list[list[float]]:
        preparados = [f"title: none | text: {texto}" for texto in textos]
        return self._embed(preparados)

    def embed_consulta(self, consulta: str) -> list[float]:
        preparado = f"task: question answering | query: {consulta}"
        return self._embed([preparado])[0]

    def _embed(self, textos: list[str]) -> list[list[float]]:
        if not textos:
            return []

        vectores: list[list[float]] = []
        for inicio in range(0, len(textos), TAMANO_LOTE):
            vectores.extend(self._embed_lote(textos[inicio : inicio + TAMANO_LOTE]))
        return vectores

    def _embed_lote(self, textos: list[str]) -> list[list[float]]:
        contenidos = [types.Content(parts=[types.Part.from_text(text=texto)]) for texto in textos]

        intento = 0
        while True:
            try:
                resultado = self.client.models.embed_content(
                    model=self.modelo,
                    contents=contenidos,
                    config=types.EmbedContentConfig(output_dimensionality=self.dimensiones),
                )
            except errors.APIError as error:
                if error.code != 429 or intento >= len(ESPERA_REINTENTOS):
                    raise
                time.sleep(ESPERA_REINTENTOS[intento])
                intento += 1
                continue

            embeddings = resultado.embeddings
            if embeddings is None:
                raise ValueError("Gemini no devolvió embeddings")

            if len(embeddings) != len(textos):
                raise ValueError(
                    f"Gemini devolvió {len(embeddings)} embeddings; se esperaban {len(textos)}"
                )

            vectores: list[list[float]] = []
            for embedding in embeddings:
                valores = embedding.values
                if valores is None:
                    raise ValueError("Gemini devolvió un embedding sin valores")

                vector = [float(valor) for valor in valores]
                if len(vector) != self.dimensiones:
                    raise ValueError(
                        f"embedding de dimensión {len(vector)}; se esperaban {self.dimensiones}"
                    )

                vectores.append(vector)

            return vectores
