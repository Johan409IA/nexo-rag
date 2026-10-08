from tests.contratos.vector_store import ContratoVectorStore
from tests.fakes import FakeEmbedder, InMemoryVectorStore


class TestInMemoryVectorStore(ContratoVectorStore):
    def crear_store(self) -> InMemoryVectorStore:
        return InMemoryVectorStore()


def test_fake_embedder_cumple_dimension_768() -> None:
    embedder = FakeEmbedder()

    documentos = embedder.embed_documentos(["cohesión", "acoplamiento"])
    consulta = embedder.embed_consulta("cohesión")

    assert [len(vector) for vector in documentos] == [768, 768]
    assert len(consulta) == 768
    assert embedder.embed_documentos([]) == []
