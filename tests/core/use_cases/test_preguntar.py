import pytest

from core.models import Documento, Fragmento, Fuente
from core.use_cases.buscar_fragmentos import BuscarFragmentos
from core.use_cases.preguntar import MENSAJE_SIN_EVIDENCIA, Preguntar
from tests.fakes import FakeEmbedder, FakeLLM, InMemoryVectorStore

HASH_UNO = "a" * 64
HASH_DOS = "b" * 64


def _insertar(
    embedder: FakeEmbedder,
    store: InMemoryVectorStore,
    *,
    hash_sha256: str,
    nombre: str,
    curso: str,
    paginas: list[tuple[int, str, int]],
) -> None:
    documento = Documento(id=None, nombre=nombre, curso=curso, hash_sha256=hash_sha256)
    fragmentos = [
        Fragmento(id=None, documento_id=None, texto=texto, pagina=pagina, chunk_index=indice)
        for pagina, texto, indice in paginas
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
        paginas=[
            (2, "cohesión y acoplamiento", 0),
            (2, "cohesión y acoplamiento: segunda parte", 1),
            (5, "principios de diseño", 0),
        ],
    )
    _insertar(
        embedder,
        store,
        hash_sha256=HASH_DOS,
        nombre="clase-02.pdf",
        curso="Bases de Datos",
        paginas=[(1, "índices y consultas", 0)],
    )
    return store


def test_prompt_incluye_contexto_y_pregunta(
    embedder: FakeEmbedder, store: InMemoryVectorStore
) -> None:
    caso = Preguntar(buscar=BuscarFragmentos(embedder=embedder, store=store), llm=FakeLLM())

    caso.ejecutar("¿Qué es cohesión?")

    prompt = caso.llm.prompts[-1]
    assert "Contexto:" in prompt
    assert "Pregunta: ¿Qué es cohesión?" in prompt
    assert "[Diseño de Software, clase-01.pdf, p. 2]" in prompt
    assert "cohesión y acoplamiento" in prompt


def test_fuentes_deduplicadas_en_orden_estable(
    embedder: FakeEmbedder, store: InMemoryVectorStore
) -> None:
    caso = Preguntar(buscar=BuscarFragmentos(embedder=embedder, store=store), llm=FakeLLM())

    resultado = caso.ejecutar("cohesión")

    claves = [(fuente.documento, fuente.curso, fuente.pagina) for fuente in resultado.fuentes]
    assert len(claves) == len(set(claves))
    assert resultado.fuentes[0] == Fuente(
        documento="clase-01.pdf", curso="Diseño de Software", pagina=2
    )
    assert len(resultado.fuentes) == 3


def test_sin_resultados_devuelve_mensaje_fijo_sin_llamar_al_llm(
    embedder: FakeEmbedder,
) -> None:
    llm = FakeLLM()
    caso = Preguntar(
        buscar=BuscarFragmentos(embedder=embedder, store=InMemoryVectorStore()), llm=llm
    )

    resultado = caso.ejecutar("¿Qué es cohesión?")

    assert resultado.respuesta == MENSAJE_SIN_EVIDENCIA
    assert resultado.fuentes == []
    assert llm.prompts == []


def test_embedding_de_consulta_se_genera_incluso_sin_resultados(
    embedder: FakeEmbedder,
) -> None:
    caso = Preguntar(
        buscar=BuscarFragmentos(embedder=embedder, store=InMemoryVectorStore()), llm=FakeLLM()
    )

    caso.ejecutar("¿Qué es cohesión?")

    assert embedder.llamadas_consulta == ["¿Qué es cohesión?"]


def test_texto_del_llm_se_devuelve_intacto(
    embedder: FakeEmbedder, store: InMemoryVectorStore
) -> None:
    llm = FakeLLM(respuesta="  respuesta con espacios  ")
    caso = Preguntar(buscar=BuscarFragmentos(embedder=embedder, store=store), llm=llm)

    resultado = caso.ejecutar("cohesión")

    assert resultado.respuesta == "  respuesta con espacios  "
