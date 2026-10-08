from types import SimpleNamespace

import pytest
from google.genai import errors, types

import adapters.ai.gemini_embedder as modulo_embedder
from adapters.ai.gemini_embedder import ESPERA_REINTENTOS, TAMANO_LOTE, GeminiEmbedder


class _ModelosFake:
    def __init__(self, resultados: list) -> None:
        self._resultados = list(resultados)
        self.llamadas: list[tuple[list[str], types.EmbedContentConfig]] = []
        self.modelos_usados: list[str] = []

    def embed_content(
        self,
        *,
        model: str,
        contents: list[types.Content],
        config: types.EmbedContentConfig,
    ):
        self.modelos_usados.append(model)

        textos: list[str] = []
        for contenido in contents:
            partes = contenido.parts
            if not partes:
                raise ValueError("El contenido no tiene partes")

            texto = partes[0].text
            if texto is None:
                raise ValueError("La parte no tiene texto")

            textos.append(texto)

        self.llamadas.append((textos, config))

        siguiente = self._resultados.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente


def _respuesta(valores: list[list[float]]) -> SimpleNamespace:
    return SimpleNamespace(embeddings=[SimpleNamespace(values=v) for v in valores])


def _error_cuota() -> errors.ClientError:
    return errors.ClientError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}, None
    )


def _embedder(monkeypatch, resultados: list) -> tuple[GeminiEmbedder, _ModelosFake]:
    modelos = _ModelosFake(resultados)
    api_keys: list[str | None] = []

    def fabrica(*, api_key: str | None = None):
        api_keys.append(api_key)
        return SimpleNamespace(models=modelos)

    monkeypatch.setattr(modulo_embedder.genai, "Client", fabrica)
    return GeminiEmbedder(api_key="clave-de-prueba"), modelos


def test_embed_documentos_aplica_prefijo_de_documento(monkeypatch) -> None:
    embedder, modelos = _embedder(monkeypatch, [_respuesta([[0.5] * 768])])

    vectores = embedder.embed_documentos(["cohesión"])

    assert modelos.llamadas[0][0] == ["title: none | text: cohesión"]
    assert modelos.llamadas[0][1].output_dimensionality == 768
    assert vectores == [[0.5] * 768]


def test_embed_consulta_aplica_prefijo_de_consulta(monkeypatch) -> None:
    embedder, modelos = _embedder(monkeypatch, [_respuesta([[0.5] * 768])])

    vector = embedder.embed_consulta("qué es la cohesión")

    assert modelos.llamadas[0][0] == ["task: question answering | query: qué es la cohesión"]
    assert vector == [0.5] * 768


def test_lista_vacia_no_llama_a_la_api(monkeypatch) -> None:
    embedder, modelos = _embedder(monkeypatch, [])

    assert embedder.embed_documentos([]) == []
    assert modelos.llamadas == []


def test_procesa_por_lotes_y_conserva_el_orden(monkeypatch) -> None:
    textos = [f"texto {i}" for i in range(TAMANO_LOTE + 10)]
    resultados = [
        _respuesta([[float(i)] * 768 for i in range(TAMANO_LOTE)]),
        _respuesta([[9.0] * 768 for _ in range(10)]),
    ]
    embedder, modelos = _embedder(monkeypatch, resultados)

    vectores = embedder.embed_documentos(textos)

    assert [len(lote) for lote, _ in modelos.llamadas] == [TAMANO_LOTE, 10]
    assert len(vectores) == TAMANO_LOTE + 10
    assert vectores[0] == [0.0] * 768
    assert vectores[-1] == [9.0] * 768


def test_reintenta_con_espera_ante_error_de_cuota(monkeypatch) -> None:
    esperas: list[float] = []
    monkeypatch.setattr(modulo_embedder.time, "sleep", esperas.append)
    embedder, modelos = _embedder(monkeypatch, [_error_cuota(), _respuesta([[0.5] * 768])])

    vectores = embedder.embed_documentos(["cohesión"])

    assert vectores == [[0.5] * 768]
    assert len(modelos.llamadas) == 2
    assert esperas == [ESPERA_REINTENTOS[0]]


def test_agota_reintentos_y_propaga_el_error_de_cuota(monkeypatch) -> None:
    esperas: list[float] = []
    monkeypatch.setattr(modulo_embedder.time, "sleep", esperas.append)
    embedder, _ = _embedder(monkeypatch, [_error_cuota() for _ in range(4)])

    with pytest.raises(errors.ClientError):
        embedder.embed_documentos(["cohesión"])

    assert esperas == list(ESPERA_REINTENTOS)


def test_no_reintenta_errores_distintos_de_cuota(monkeypatch) -> None:
    esperas: list[float] = []
    monkeypatch.setattr(modulo_embedder.time, "sleep", esperas.append)
    error = errors.ClientError(400, {"error": {"code": 400, "message": "bad request"}}, None)
    embedder, _ = _embedder(monkeypatch, [error])

    with pytest.raises(errors.ClientError):
        embedder.embed_documentos(["cohesión"])

    assert esperas == []


def test_valida_la_dimension_de_los_vectores(monkeypatch) -> None:
    embedder, _ = _embedder(monkeypatch, [_respuesta([[0.5] * 3])])

    with pytest.raises(ValueError, match="dimensión"):
        embedder.embed_documentos(["cohesión"])


def test_respuesta_sin_embeddings_falla_con_error_claro(monkeypatch) -> None:
    embedder, _ = _embedder(monkeypatch, [SimpleNamespace(embeddings=None)])

    with pytest.raises(ValueError, match="no devolvió embeddings"):
        embedder.embed_documentos(["cohesión"])


def test_embedding_sin_valores_falla_con_error_claro(monkeypatch) -> None:
    embedder, _ = _embedder(
        monkeypatch, [SimpleNamespace(embeddings=[SimpleNamespace(values=None)])]
    )

    with pytest.raises(ValueError, match="sin valores"):
        embedder.embed_documentos(["cohesión"])


def test_convierte_valores_numericos_a_float(monkeypatch) -> None:
    embedder, _ = _embedder(monkeypatch, [_respuesta([[1] * 768])])

    vector = embedder.embed_documentos(["cohesión"])[0]

    assert all(type(valor) is float for valor in vector)
