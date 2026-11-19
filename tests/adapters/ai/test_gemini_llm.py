from types import SimpleNamespace

import pytest
from google.genai import errors

import adapters.ai.gemini_llm as modulo_llm
from adapters.ai.gemini_llm import ESPERA_REINTENTOS, MODELO_LLM, GeminiLLM


class _ModelosFake:
    def __init__(self, resultados: list) -> None:
        self._resultados = list(resultados)
        self.llamadas: list[tuple[str, str]] = []

    def generate_content(self, *, model: str, contents: str):
        self.llamadas.append((model, contents))

        siguiente = self._resultados.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente


def _llm(monkeypatch, resultados: list) -> tuple[GeminiLLM, _ModelosFake]:
    modelos = _ModelosFake(resultados)

    def fabrica(*, api_key: str | None = None):
        return SimpleNamespace(models=modelos)

    monkeypatch.setattr(modulo_llm.genai, "Client", fabrica)
    return GeminiLLM(api_key="clave-de-prueba"), modelos


def test_responder_envia_el_prompt_y_devuelve_el_texto(monkeypatch) -> None:
    llm, modelos = _llm(monkeypatch, [SimpleNamespace(text="La cohesión describe...")])

    texto = llm.responder("Contexto:\n...\n\nPregunta: ¿Qué es la cohesión?")

    assert texto == "La cohesión describe..."
    assert modelos.llamadas == [
        (MODELO_LLM, "Contexto:\n...\n\nPregunta: ¿Qué es la cohesión?"),
    ]


def test_modelo_configurable_por_constructor(monkeypatch) -> None:
    modelos = _ModelosFake([SimpleNamespace(text="ok")])

    def fabrica(*, api_key: str | None = None):
        return SimpleNamespace(models=modelos)

    monkeypatch.setattr(modulo_llm.genai, "Client", fabrica)
    llm = GeminiLLM(api_key="clave-de-prueba", modelo="gemini-otro")

    llm.responder("hola")

    assert llm.modelo == "gemini-otro"
    assert modelos.llamadas[0][0] == "gemini-otro"


def test_respuesta_nula_falla_con_error_claro(monkeypatch) -> None:
    llm, _ = _llm(monkeypatch, [SimpleNamespace(text=None)])

    with pytest.raises(ValueError, match="no devolvió texto"):
        llm.responder("pregunta")


def test_respuesta_vacia_falla_con_error_claro(monkeypatch) -> None:
    llm, _ = _llm(monkeypatch, [SimpleNamespace(text="")])

    with pytest.raises(ValueError, match="no devolvió texto"):
        llm.responder("pregunta")


def _error_alta_demanda() -> errors.ServerError:
    return errors.ServerError(
        503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}}, None
    )


def test_reintenta_con_espera_ante_alta_demanda(monkeypatch) -> None:
    esperas: list[float] = []
    monkeypatch.setattr(modulo_llm.time, "sleep", esperas.append)
    llm, modelos = _llm(monkeypatch, [_error_alta_demanda(), SimpleNamespace(text="respuesta")])

    assert llm.responder("pregunta") == "respuesta"
    assert len(modelos.llamadas) == 2
    assert esperas == [ESPERA_REINTENTOS[0]]


def test_agota_reintentos_y_propaga_el_error_de_alta_demanda(monkeypatch) -> None:
    esperas: list[float] = []
    monkeypatch.setattr(modulo_llm.time, "sleep", esperas.append)
    llm, _ = _llm(monkeypatch, [_error_alta_demanda() for _ in range(len(ESPERA_REINTENTOS) + 1)])

    with pytest.raises(errors.ServerError):
        llm.responder("pregunta")

    assert esperas == list(ESPERA_REINTENTOS)


def test_no_reintenta_errores_distintos_de_cuota_o_alta_demanda(monkeypatch) -> None:
    esperas: list[float] = []
    monkeypatch.setattr(modulo_llm.time, "sleep", esperas.append)
    error = errors.ClientError(400, {"error": {"code": 400, "message": "bad request"}}, None)
    llm, _ = _llm(monkeypatch, [error])

    with pytest.raises(errors.ClientError):
        llm.responder("pregunta")

    assert esperas == []
