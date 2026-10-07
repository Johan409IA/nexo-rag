import zlib

DIMENSIONES = 768


class FakeEmbedder:
    """Embedder sintético determinista de 768 dimensiones.

    Construye una bolsa de palabras hasheada con ``zlib.crc32`` (nunca con
    ``hash()``, que varía entre procesos) y la normaliza L2, de modo que textos
    parecidos producen vectores parecidos. Respeta cardinalidad y orden del
    contrato de ``Embedder``.
    """

    def __init__(self) -> None:
        self.llamadas_documentos: list[list[str]] = []
        self.llamadas_consulta: list[str] = []

    def embed_documentos(self, textos: list[str]) -> list[list[float]]:
        self.llamadas_documentos.append(list(textos))
        return [self._vector(texto) for texto in textos]

    def embed_consulta(self, consulta: str) -> list[float]:
        self.llamadas_consulta.append(consulta)
        return self._vector(consulta)


    @staticmethod
    def _vector(texto: str) -> list[float]:
        vector = [0.0] * DIMENSIONES
        for palabra in texto.lower().split():
            indice = zlib.crc32(palabra.encode("utf-8")) % DIMENSIONES
            vector[indice] += 1.0

        norma = sum(valor * valor for valor in vector) ** 0.5
        if norma == 0.0:
            return vector
        return [valor / norma for valor in vector]
