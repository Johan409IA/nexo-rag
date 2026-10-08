import uuid

import pytest

from core.models import Documento, Fragmento
from core.ports.vector_store import VectorStore
from core.use_cases.ingestar_documento import DocumentoDuplicadoError
from tests.fakes import FakeEmbedder

MARCADOR = uuid.uuid4().hex[:8]
HASH_UNO = uuid.uuid4().hex + uuid.uuid4().hex
HASH_DOS = uuid.uuid4().hex + uuid.uuid4().hex
CURSO = f"contrato {MARCADOR}"
CURSO_A = f"contrato A {MARCADOR}"
CURSO_B = f"contrato B {MARCADOR}"


def documento(hash_sha256: str, nombre: str = "x.pdf", curso: str = CURSO) -> Documento:
    return Documento(id=None, nombre=nombre, curso=curso, hash_sha256=hash_sha256)


def fragmento(texto: str, pagina: int) -> Fragmento:
    return Fragmento(id=None, documento_id=None, texto=texto, pagina=pagina, chunk_index=0)


class ContratoVectorStore:
    """Contrato del puerto ``VectorStore`` reutilizable entre implementaciones.

    Cada clase que la hereda define ``crear_store()``, que devuelve un almacén
    vacío de los marcadores de este contrato. Los datos de prueba llevan un
    marcador único por ejecución para no interferir con otros datos del almacén.
    """

    def crear_store(self) -> VectorStore:
        raise NotImplementedError

    @staticmethod
    def guardar(
        store: VectorStore,
        documento_a_guardar: Documento,
        fragmentos: list[Fragmento],
    ) -> None:
        embedder = FakeEmbedder()
        embeddings = embedder.embed_documentos(
            [fragmento_item.texto for fragmento_item in fragmentos]
        )
        store.guardar_documento_con_fragmentos(
            documento_a_guardar,
            fragmentos,
            embeddings,
        )

    def test_existe_hash(self) -> None:
        store = self.crear_store()

        assert store.existe_hash(HASH_UNO) is False

        self.guardar(store, documento(HASH_UNO), [fragmento("cohesión", 1)])

        assert store.existe_hash(HASH_UNO) is True
        assert store.existe_hash(HASH_DOS) is False

    def test_guardar_rechaza_hash_duplicado(self) -> None:
        embedder = FakeEmbedder()
        store = self.crear_store()
        self.guardar(store, documento(HASH_UNO), [fragmento("cohesión", 1)])

        with pytest.raises(DocumentoDuplicadoError):
            self.guardar(store, documento(HASH_UNO, nombre="otro.pdf"), [fragmento("otra", 2)])

        resultados = store.buscar(embedder.embed_consulta("otra"), k=10, curso=CURSO)
        assert [resultado.documento for resultado in resultados] == ["x.pdf"]

    def test_guardar_es_atomico_con_longitudes_distintas(self) -> None:
        embedder = FakeEmbedder()
        store = self.crear_store()
        documento_a_guardar = documento(HASH_UNO)
        fragmentos = [fragmento("cohesión", 1), fragmento("acoplamiento", 2)]
        embeddings = embedder.embed_documentos(["cohesión"])

        with pytest.raises(ValueError, match="longitud"):
            store.guardar_documento_con_fragmentos(documento_a_guardar, fragmentos, embeddings)

        assert store.existe_hash(HASH_UNO) is False
        assert store.buscar(embedder.embed_consulta("cohesión"), k=10, curso=CURSO) == []

    def test_buscar_respeta_k(self) -> None:
        embedder = FakeEmbedder()
        store = self.crear_store()
        self.guardar(
            store,
            documento(HASH_UNO),
            [fragmento("cohesión", 1), fragmento("acoplamiento", 2), fragmento("diseño", 3)],
        )

        resultados = store.buscar(embedder.embed_consulta("cohesión"), k=2, curso=CURSO)

        assert len(resultados) == 2

    def test_buscar_filtra_por_curso(self) -> None:
        embedder = FakeEmbedder()
        store = self.crear_store()
        self.guardar(
            store,
            documento(HASH_UNO, nombre="a.pdf", curso=CURSO_A),
            [fragmento("cohesión", 1)],
        )
        self.guardar(
            store,
            documento(HASH_DOS, nombre="b.pdf", curso=CURSO_B),
            [fragmento("cohesión", 1)],
        )

        resultados = store.buscar(embedder.embed_consulta("cohesión"), k=10, curso=CURSO_B)

        assert [resultado.documento for resultado in resultados] == ["b.pdf"]

    def test_buscar_ordena_por_score_descendente(self) -> None:
        embedder = FakeEmbedder()
        store = self.crear_store()
        self.guardar(
            store,
            documento(HASH_UNO),
            [fragmento("cohesión y acoplamiento", 1), fragmento("temas sin relación", 2)],
        )

        resultados = store.buscar(
            embedder.embed_consulta("cohesión y acoplamiento"), k=10, curso=CURSO
        )

        scores = [resultado.score for resultado in resultados]
        assert scores == sorted(scores, reverse=True)
        assert resultados[0].pagina == 1
