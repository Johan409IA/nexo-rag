import importlib.util
import json
from pathlib import Path

import pytest

from core.models.resultado_busqueda import ResultadoBusqueda
from core.use_cases.buscar_fragmentos import BuscarFragmentos
from tests.fakes import FakeEmbedder, FakeLLM, InMemoryVectorStore

_RUTA_EVALUATE = Path(__file__).resolve().parents[2] / "eval" / "evaluate.py"
_especificacion = importlib.util.spec_from_file_location("evaluate", _RUTA_EVALUATE)
evaluate = importlib.util.module_from_spec(_especificacion)
_especificacion.loader.exec_module(evaluate)


def _resultado(documento: str, pagina: int, score: float) -> ResultadoBusqueda:
    return ResultadoBusqueda(
        texto="texto", documento=documento, curso="Curso", pagina=pagina, score=score
    )


def _pregunta(
    categoria: str = "directa",
    documento: str | None = "doc.pdf",
    paginas: tuple[int, ...] = (3,),
    identificador: str = "P01",
) -> evaluate.PreguntaEval:
    return evaluate.PreguntaEval(
        id=identificador,
        pregunta="¿Pregunta?",
        curso="Curso",
        categoria=categoria,
        documento=documento,
        paginas_esperadas=paginas,
        respuesta_referencia="referencia",
    )


def _entrada_dataset(**cambios) -> dict:
    entrada = {
        "id": "P01",
        "pregunta": "¿Pregunta?",
        "curso": "Curso",
        "categoria": "directa",
        "documento": "doc.pdf",
        "paginas_esperadas": [3],
        "respuesta_referencia": "referencia",
    }
    entrada.update(cambios)
    return entrada


def _guardar_dataset(tmp_path: Path, entradas: list) -> Path:
    ruta = tmp_path / "dataset.json"
    ruta.write_text(json.dumps(entradas, ensure_ascii=False), encoding="utf-8")
    return ruta


# --- Métricas de retrieval -------------------------------------------------


def test_hit_en_primera_posicion() -> None:
    resultados = [_resultado("doc.pdf", 3, 0.9), _resultado("otro.pdf", 1, 0.8)]

    posicion = evaluate.calcular_posicion(resultados, "doc.pdf", (3,))

    assert posicion == 1


def test_hit_en_la_ultima_posicion_del_top_k() -> None:
    resultados = [
        _resultado("a.pdf", 1, 0.9),
        _resultado("b.pdf", 2, 0.8),
        _resultado("c.pdf", 3, 0.7),
        _resultado("doc.pdf", 3, 0.6),
    ]

    assert evaluate.calcular_posicion(resultados, "doc.pdf", (3,)) == 4


def test_fallo_si_la_pagina_esperada_no_aparece() -> None:
    resultados = [_resultado("doc.pdf", 7, 0.9), _resultado("otro.pdf", 3, 0.8)]

    assert evaluate.calcular_posicion(resultados, "doc.pdf", (3,)) is None


def test_cobertura_parcial_en_multi_pagina() -> None:
    resultados = [_resultado("doc.pdf", 8, 0.9), _resultado("doc.pdf", 5, 0.8)]

    assert evaluate.calcular_cobertura(resultados, "doc.pdf", (8, 9)) == 0.5


def test_evaluar_pregunta_directa_calcula_hit_y_score() -> None:
    pregunta = _pregunta()
    resultados = [_resultado("otro.pdf", 1, 0.9), _resultado("doc.pdf", 3, 0.8)]

    evaluacion = evaluate.evaluar_pregunta(pregunta, resultados)

    assert evaluacion.hit is True
    assert evaluacion.posicion == 2
    assert evaluacion.cobertura is None
    assert evaluacion.score_primer_acierto == 0.8
    assert evaluacion.scores == (0.9, 0.8)


def test_evaluar_pregunta_multi_pagina_calcula_cobertura() -> None:
    pregunta = _pregunta(categoria="multi_pagina", paginas=(8, 9))
    resultados = [_resultado("doc.pdf", 8, 0.9), _resultado("doc.pdf", 5, 0.8)]

    evaluacion = evaluate.evaluar_pregunta(pregunta, resultados)

    assert evaluacion.hit is True
    assert evaluacion.cobertura == 0.5


def test_evaluar_pregunta_sin_respuesta_no_calcula_hit() -> None:
    pregunta = _pregunta(categoria="sin_respuesta", documento=None, paginas=())
    resultados = [_resultado("doc.pdf", 3, 0.4)]

    evaluacion = evaluate.evaluar_pregunta(pregunta, resultados)

    assert evaluacion.hit is None
    assert evaluacion.posicion is None
    assert evaluacion.cobertura is None
    assert evaluacion.scores == (0.4,)


def test_resumen_agrupa_por_categoria() -> None:
    evaluaciones = [
        evaluate.evaluar_pregunta(
            _pregunta("directa", paginas=(1,), identificador="P01"), [_resultado("doc.pdf", 1, 0.9)]
        ),
        evaluate.evaluar_pregunta(
            _pregunta("directa", paginas=(2,), identificador="P02"), [_resultado("doc.pdf", 9, 0.9)]
        ),
        evaluate.evaluar_pregunta(
            _pregunta("multi_pagina", paginas=(1, 2), identificador="P03"),
            [_resultado("doc.pdf", 1, 0.9)],
        ),
        evaluate.evaluar_pregunta(
            _pregunta("sin_respuesta", documento=None, paginas=(), identificador="P04"),
            [_resultado("doc.pdf", 3, 0.2)],
        ),
    ]

    resumen = evaluate.resumir(evaluaciones)

    assert resumen.total == 4
    assert resumen.aplicables == 3
    assert resumen.hits == 2
    assert resumen.hit_at_k == pytest.approx(2 / 3)
    assert resumen.hit_at_k_por_categoria["directa"] == pytest.approx(0.5)
    assert resumen.hit_at_k_por_categoria["multi_pagina"] == pytest.approx(1.0)
    assert resumen.posicion_media == 1
    assert resumen.cobertura_media == pytest.approx(0.5)
    assert resumen.scores_max_sin_respuesta == (0.2,)


# --- Validación del dataset ------------------------------------------------


def test_cargar_dataset_valido(tmp_path: Path) -> None:
    ruta = _guardar_dataset(
        tmp_path,
        [
            _entrada_dataset(),
            _entrada_dataset(
                id="P02",
                categoria="sin_respuesta",
                documento=None,
                paginas_esperadas=[],
            ),
        ],
    )

    preguntas = evaluate.cargar_dataset(ruta)

    assert [p.id for p in preguntas] == ["P01", "P02"]
    assert preguntas[1].documento is None
    assert preguntas[1].paginas_esperadas == ()


def test_dataset_rechaza_categoria_invalida(tmp_path: Path) -> None:
    ruta = _guardar_dataset(tmp_path, [_entrada_dataset(categoria="ambigua")])

    with pytest.raises(evaluate.DatasetInvalidoError, match="categoría inválida"):
        evaluate.cargar_dataset(ruta)


def test_dataset_rechaza_directa_sin_paginas(tmp_path: Path) -> None:
    ruta = _guardar_dataset(tmp_path, [_entrada_dataset(paginas_esperadas=[])])

    with pytest.raises(evaluate.DatasetInvalidoError, match="al menos una página"):
        evaluate.cargar_dataset(ruta)


def test_dataset_rechaza_pagina_invalida(tmp_path: Path) -> None:
    ruta = _guardar_dataset(tmp_path, [_entrada_dataset(paginas_esperadas=[0])])

    with pytest.raises(evaluate.DatasetInvalidoError, match="página inválida"):
        evaluate.cargar_dataset(ruta)


def test_dataset_rechaza_sin_respuesta_con_documento(tmp_path: Path) -> None:
    ruta = _guardar_dataset(
        tmp_path, [_entrada_dataset(categoria="sin_respuesta", paginas_esperadas=[])]
    )

    with pytest.raises(evaluate.DatasetInvalidoError, match="no debe llevar 'documento'"):
        evaluate.cargar_dataset(ruta)


def test_dataset_rechaza_ids_duplicados(tmp_path: Path) -> None:
    ruta = _guardar_dataset(tmp_path, [_entrada_dataset(), _entrada_dataset()])

    with pytest.raises(evaluate.DatasetInvalidoError, match="duplicados"):
        evaluate.cargar_dataset(ruta)


# --- Fallback sin evidencia ------------------------------------------------


def test_fallback_retrieval_vacio_no_llama_al_llm() -> None:
    buscar = BuscarFragmentos(embedder=FakeEmbedder(), store=InMemoryVectorStore())
    llm = FakeLLM()

    resultado = evaluate.comprobar_fallback(buscar, llm)

    assert resultado.correcto is True
    assert resultado.respuesta == evaluate.MENSAJE_SIN_EVIDENCIA
    assert resultado.fuentes == ()
    assert resultado.llamadas_llm == 0
    assert llm.prompts == []
