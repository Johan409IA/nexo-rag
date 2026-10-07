import pytest

from core.models import Documento, Fragmento
from core.use_cases.buscar_fragmentos import K_POR_DEFECTO, BuscarFragmentos
from tests.fakes import FakeEmbedder, InMemoryVectorStore

HASH_UNO = "a" * 64
HASH_DOS = "b" * 64
HASH_TRES = "c" * 64


def _insertar(
    embedder: FakeEmbedder,
    store: InMemoryVectorStore,
    *,
    hash_sha256: str,
    nombre: str,
    curso: str,
    paginas: list[tuple[int, str]],
) -> None:
    documento = Documento(id=None, nombre=nombre, curso=curso, hash_sha256=hash_sha256)
    fragmentos = [
        Fragmento(id=None, documento_id=None, texto=texto, pagina=pagina, chunk_index=0)
        for pagina, texto in paginas
    ]
    embeddings = embedder.embed_documentos([fragmento.texto for fragmento in fragmentos])
    store.guardar_documento_con_fragmentos(documento, fragmentos, embeddings)


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def store(embedder: FakeEmbedder) -> InMemoryVectorStore:
    store = InMemoryVectorStore()
    _insertar(
        embedder,
        store,
        hash_sha256=HASH_UNO,
        nombre="clase-01.pdf",
        curso="Diseño de Software",
        paginas=[(1, "cohesión y acoplamiento"), (2, "principios de diseño")],
    )
    _insertar(
        embedder,
        store,
        hash_sha256=HASH_DOS,
        nombre="clase-02.pdf",
        curso="Bases de Datos",
        paginas=[(1, "índices y consultas"), (2, "cohesión en tablas")],
    )
    return store


def test_k_por_defecto_es_cuatro() -> None:
    assert K_POR_DEFECTO == 4


def test_usa_embed_consulta_y_no_embed_documentos() -> None:
    embedder = FakeEmbedder()
    caso = BuscarFragmentos(embedder=embedder, store=InMemoryVectorStore())

    caso.ejecutar("cohesión")

    assert embedder.llamadas_consulta == ["cohesión"]
    assert embedder.llamadas_documentos == []


def test_respeta_k(embedder: FakeEmbedder, store: InMemoryVectorStore) -> None:
    caso = BuscarFragmentos(embedder=embedder, store=store)

    resultados = caso.ejecutar("cohesión y diseño", k=2)

    assert len(resultados) == 2


def test_filtra_por_curso(embedder: FakeEmbedder, store: InMemoryVectorStore) -> None:
    caso = BuscarFragmentos(embedder=embedder, store=store)

    resultados = caso.ejecutar("cohesión", curso="Diseño de Software")

    assert resultados
    assert all(resultado.curso == "Diseño de Software" for resultado in resultados)


def test_ordena_por_score_descendente(embedder: FakeEmbedder, store: InMemoryVectorStore) -> None:
    caso = BuscarFragmentos(embedder=embedder, store=store)

    resultados = caso.ejecutar("cohesión y acoplamiento")

    scores = [resultado.score for resultado in resultados]
    assert scores == sorted(scores, reverse=True)
    assert resultados[0].documento == "clase-01.pdf"


@pytest.mark.parametrize("consulta", ["", "   "])
def test_rechaza_consulta_vacia(embedder: FakeEmbedder, consulta: str) -> None:
    caso = BuscarFragmentos(embedder=embedder, store=InMemoryVectorStore())

    with pytest.raises(ValueError, match="consulta"):
        caso.ejecutar(consulta)


def test_rechaza_k_menor_que_uno(embedder: FakeEmbedder) -> None:
    caso = BuscarFragmentos(embedder=embedder, store=InMemoryVectorStore())

    with pytest.raises(ValueError, match="k"):
        caso.ejecutar("cohesión", k=0)
