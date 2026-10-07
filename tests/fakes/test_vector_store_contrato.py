import pytest

from core.models import Documento, Fragmento
from core.use_cases.ingestar_documento import DocumentoDuplicadoError
from tests.fakes import FakeEmbedder, InMemoryVectorStore

HASH_UNO = "a" * 64
HASH_DOS = "b" * 64


def _documento(hash_sha256: str, nombre: str = "x.pdf", curso: str = "curso") -> Documento:
    return Documento(id=None, nombre=nombre, curso=curso, hash_sha256=hash_sha256)


def _fragmento(texto: str, pagina: int) -> Fragmento:
    return Fragmento(id=None, documento_id=None, texto=texto, pagina=pagina, chunk_index=0)


def _guardar(
    embedder: FakeEmbedder,
    store: InMemoryVectorStore,
    documento: Documento,
    fragmentos: list[Fragmento],
) -> None:
    embeddings = embedder.embed_documentos([fragmento.texto for fragmento in fragmentos])
    store.guardar_documento_con_fragmentos(documento, fragmentos, embeddings)


def test_existe_hash() -> None:
    embedder = FakeEmbedder()
    store = InMemoryVectorStore()

    assert store.existe_hash(HASH_UNO) is False

    _guardar(embedder, store, _documento(HASH_UNO), [_fragmento("cohesión", 1)])

    assert store.existe_hash(HASH_UNO) is True
    assert store.existe_hash(HASH_DOS) is False


def test_guardar_rechaza_hash_duplicado() -> None:
    embedder = FakeEmbedder()
    store = InMemoryVectorStore()
    _guardar(embedder, store, _documento(HASH_UNO), [_fragmento("cohesión", 1)])

    with pytest.raises(DocumentoDuplicadoError):
        _guardar(embedder, store, _documento(HASH_UNO, nombre="otro.pdf"), [_fragmento("otra", 2)])

    assert store.buscar(embedder.embed_consulta("otra"), k=10)[0].documento == "x.pdf"


def test_guardar_es_atomico_con_longitudes_distintas() -> None:
    embedder = FakeEmbedder()
    store = InMemoryVectorStore()
    documento = _documento(HASH_UNO)
    fragmentos = [_fragmento("cohesión", 1), _fragmento("acoplamiento", 2)]
    embeddings = embedder.embed_documentos(["cohesión"])

    with pytest.raises(ValueError, match="longitud"):
        store.guardar_documento_con_fragmentos(documento, fragmentos, embeddings)

    assert store.existe_hash(HASH_UNO) is False
    assert store.buscar(embedder.embed_consulta("cohesión"), k=10) == []


def test_buscar_respeta_k() -> None:
    embedder = FakeEmbedder()
    store = InMemoryVectorStore()
    _guardar(
        embedder,
        store,
        _documento(HASH_UNO),
        [_fragmento("cohesión", 1), _fragmento("acoplamiento", 2), _fragmento("diseño", 3)],
    )

    resultados = store.buscar(embedder.embed_consulta("cohesión"), k=2)

    assert len(resultados) == 2


def test_buscar_filtra_por_curso() -> None:
    embedder = FakeEmbedder()
    store = InMemoryVectorStore()
    _guardar(
        embedder,
        store,
        _documento(HASH_UNO, nombre="a.pdf", curso="Curso A"),
        [_fragmento("cohesión", 1)],
    )
    _guardar(
        embedder,
        store,
        _documento(HASH_DOS, nombre="b.pdf", curso="Curso B"),
        [_fragmento("cohesión", 1)],
    )

    resultados = store.buscar(embedder.embed_consulta("cohesión"), k=10, curso="Curso B")

    assert [resultado.documento for resultado in resultados] == ["b.pdf"]


def test_buscar_ordena_por_score_descendente() -> None:
    embedder = FakeEmbedder()
    store = InMemoryVectorStore()
    _guardar(
        embedder,
        store,
        _documento(HASH_UNO),
        [_fragmento("cohesión y acoplamiento", 1), _fragmento("temas sin relación", 2)],
    )

    resultados = store.buscar(embedder.embed_consulta("cohesión y acoplamiento"), k=10)

    scores = [resultado.score for resultado in resultados]
    assert scores == sorted(scores, reverse=True)
    assert resultados[0].pagina == 1


def test_fake_embedder_cumple_dimension_768() -> None:
    embedder = FakeEmbedder()

    documentos = embedder.embed_documentos(["cohesión", "acoplamiento"])
    consulta = embedder.embed_consulta("cohesión")

    assert [len(vector) for vector in documentos] == [768, 768]
    assert len(consulta) == 768
    assert embedder.embed_documentos([]) == []
