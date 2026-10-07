from core.models import Documento, Fragmento, ResultadoBusqueda
from core.use_cases.ingestar_documento import DocumentoDuplicadoError


class InMemoryVectorStore:
    """``VectorStore`` en memoria con similitud coseno para tests."""

    def __init__(self) -> None:
        self._documentos: list[Documento] = []
        self._fragmentos: list[tuple[Documento, Fragmento, list[float]]] = []

    def existe_hash(self, hash_sha256: str) -> bool:
        return any(documento.hash_sha256 == hash_sha256 for documento in self._documentos)

    def guardar_documento_con_fragmentos(
        self,
        documento: Documento,
        fragmentos: list[Fragmento],
        embeddings: list[list[float]],
    ) -> None:
        if len(fragmentos) != len(embeddings):
            raise ValueError("fragmentos y embeddings deben tener la misma longitud")
        if self.existe_hash(documento.hash_sha256):
            raise DocumentoDuplicadoError("El documento ya fue ingestado.")

        self._documentos.append(documento)
        for fragmento, embedding in zip(fragmentos, embeddings, strict=True):
            self._fragmentos.append((documento, fragmento, list(embedding)))

    def buscar(
        self,
        embedding: list[float],
        k: int = 4,
        curso: str | None = None,
    ) -> list[ResultadoBusqueda]:
        candidatos: list[ResultadoBusqueda] = []
        for documento, fragmento, vector in self._fragmentos:
            if curso is not None and documento.curso != curso:
                continue
            candidatos.append(
                ResultadoBusqueda(
                    texto=fragmento.texto,
                    documento=documento.nombre,
                    curso=documento.curso,
                    pagina=fragmento.pagina,
                    score=_similitud_coseno(embedding, vector),
                )
            )

        candidatos.sort(key=lambda resultado: resultado.score, reverse=True)
        return candidatos[:k]


def _similitud_coseno(a: list[float], b: list[float]) -> float:
    norma_a = sum(valor * valor for valor in a) ** 0.5
    norma_b = sum(valor * valor for valor in b) ** 0.5
    if norma_a == 0.0 or norma_b == 0.0:
        return 0.0
    producto = sum(x * y for x, y in zip(a, b, strict=True))
    return producto / (norma_a * norma_b)
