"""Evaluación de la Fase 2: retrieval (Hit@k) y generación sobre `eval/dataset.json`.

Uso (desde la raíz del proyecto; `--env-file .env` carga `DATABASE_URL` y
`GEMINI_API_KEY` sin exponerlos):

    uv run --env-file .env python eval/evaluate.py
    uv run --env-file .env python eval/evaluate.py --dataset eval/dataset.json --k 4

Escribe el informe en `eval/resultados/<AAAA-MM-DD>.md`.
Códigos de salida: 0 correcto, 2 configuración o uso.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models.respuesta_rag import RespuestaRAG
from core.models.resultado_busqueda import ResultadoBusqueda
from core.ports.llm import LLM
from core.use_cases.buscar_fragmentos import BuscarFragmentos
from core.use_cases.preguntar import MENSAJE_SIN_EVIDENCIA, Preguntar

CATEGORIAS = ("directa", "multi_pagina", "sin_respuesta")
K_POR_DEFECTO = 4
CURSO_SIN_RESULTADOS = "__eval_curso_inexistente__"
PREGUNTA_DE_CONTROL = "¿Pregunta de control sin resultados en la base de conocimiento?"


class DatasetInvalidoError(ValueError):
    """El dataset no cumple el esquema de `eval/dataset.json`."""


class FaltaConfiguracion(RuntimeError):
    """Faltan variables de entorno necesarias para ejecutar la evaluación."""


@dataclass(frozen=True, slots=True)
class PreguntaEval:
    id: str
    pregunta: str
    curso: str
    categoria: str
    documento: str | None
    paginas_esperadas: tuple[int, ...]
    respuesta_referencia: str


@dataclass(frozen=True, slots=True)
class EvaluacionPregunta:
    pregunta: PreguntaEval
    hit: bool | None
    posicion: int | None
    cobertura: float | None
    scores: tuple[float, ...]
    score_primer_acierto: float | None
    paginas_recuperadas: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class Resumen:
    total: int
    aplicables: int
    hits: int
    hit_at_k: float | None
    hit_at_k_por_categoria: dict[str, float]
    posicion_media: float | None
    cobertura_media: float | None
    scores_max_sin_respuesta: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ResultadoFallback:
    respuesta: str
    fuentes: tuple[tuple[str, str, int], ...]
    llamadas_llm: int
    correcto: bool


class LlmContador:
    """Envuelve un puerto ``LLM`` y cuenta las llamadas generativas."""

    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.llamadas = 0

    def responder(self, prompt: str) -> str:
        self.llamadas += 1
        return self.llm.responder(prompt)


def cargar_dataset(ruta: str | Path) -> list[PreguntaEval]:
    archivo = Path(ruta)
    with archivo.open(encoding="utf-8") as datos:
        entradas = json.load(datos)

    if not isinstance(entradas, list):
        raise DatasetInvalidoError("El dataset debe ser una lista de preguntas.")

    preguntas = [_validar_entrada(entrada, indice) for indice, entrada in enumerate(entradas, 1)]
    ids = [pregunta.id for pregunta in preguntas]
    duplicados = sorted({identificador for identificador in ids if ids.count(identificador) > 1})
    if duplicados:
        raise DatasetInvalidoError(f"ids duplicados en el dataset: {', '.join(duplicados)}")
    return preguntas


def _validar_entrada(entrada: object, indice: int) -> PreguntaEval:
    if not isinstance(entrada, dict):
        raise DatasetInvalidoError(f"La entrada {indice} no es un objeto JSON.")

    bruto = entrada.get("id")
    etiqueta = bruto if isinstance(bruto, str) and bruto else f"entrada {indice}"

    def texto(campo: str) -> str:
        valor = entrada.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise DatasetInvalidoError(f"{etiqueta}: falta el campo '{campo}' o está vacío.")
        return valor.strip()

    identificador = texto("id")
    pregunta = texto("pregunta")
    curso = texto("curso")
    categoria = texto("categoria")
    respuesta_referencia = texto("respuesta_referencia")

    if categoria not in CATEGORIAS:
        raise DatasetInvalidoError(f"{etiqueta}: categoría inválida '{categoria}'.")

    documento = entrada.get("documento")
    paginas = entrada.get("paginas_esperadas")

    if categoria == "sin_respuesta":
        if documento not in (None, ""):
            raise DatasetInvalidoError(f"{etiqueta}: 'sin_respuesta' no debe llevar 'documento'.")
        if paginas not in (None, []):
            raise DatasetInvalidoError(
                f"{etiqueta}: 'sin_respuesta' no debe llevar 'paginas_esperadas'."
            )
        documento_final = None
        paginas_finales: tuple[int, ...] = ()
    else:
        if not isinstance(documento, str) or not documento.strip():
            raise DatasetInvalidoError(f"{etiqueta}: falta el campo 'documento'.")
        if not isinstance(paginas, list) or not paginas:
            raise DatasetInvalidoError(
                f"{etiqueta}: 'paginas_esperadas' debe contener al menos una página."
            )
        for pagina in paginas:
            if isinstance(pagina, bool) or not isinstance(pagina, int) or pagina < 1:
                raise DatasetInvalidoError(f"{etiqueta}: página inválida {pagina!r}.")
        documento_final = documento.strip()
        paginas_finales = tuple(paginas)

    return PreguntaEval(
        id=identificador,
        pregunta=pregunta,
        curso=curso,
        categoria=categoria,
        documento=documento_final,
        paginas_esperadas=paginas_finales,
        respuesta_referencia=respuesta_referencia,
    )


def calcular_posicion(
    resultados: list[ResultadoBusqueda],
    documento: str | None,
    paginas_esperadas: tuple[int, ...],
) -> int | None:
    esperadas = set(paginas_esperadas)
    for posicion, resultado in enumerate(resultados, start=1):
        if resultado.documento == documento and resultado.pagina in esperadas:
            return posicion
    return None


def calcular_cobertura(
    resultados: list[ResultadoBusqueda],
    documento: str | None,
    paginas_esperadas: tuple[int, ...],
) -> float:
    esperadas = set(paginas_esperadas)
    recuperadas = {resultado.pagina for resultado in resultados if resultado.documento == documento}
    return len(esperadas & recuperadas) / len(esperadas)


def evaluar_pregunta(
    pregunta: PreguntaEval, resultados: list[ResultadoBusqueda]
) -> EvaluacionPregunta:
    scores = tuple(resultado.score for resultado in resultados)
    paginas = tuple((resultado.documento, resultado.pagina) for resultado in resultados)

    if pregunta.categoria == "sin_respuesta":
        return EvaluacionPregunta(
            pregunta=pregunta,
            hit=None,
            posicion=None,
            cobertura=None,
            scores=scores,
            score_primer_acierto=None,
            paginas_recuperadas=paginas,
        )

    posicion = calcular_posicion(resultados, pregunta.documento, pregunta.paginas_esperadas)
    cobertura = (
        calcular_cobertura(resultados, pregunta.documento, pregunta.paginas_esperadas)
        if pregunta.categoria == "multi_pagina"
        else None
    )
    return EvaluacionPregunta(
        pregunta=pregunta,
        hit=posicion is not None,
        posicion=posicion,
        cobertura=cobertura,
        scores=scores,
        score_primer_acierto=scores[posicion - 1] if posicion is not None else None,
        paginas_recuperadas=paginas,
    )


def resumir(evaluaciones: list[EvaluacionPregunta]) -> Resumen:
    aplicables = [evaluacion for evaluacion in evaluaciones if evaluacion.hit is not None]
    hits = [evaluacion for evaluacion in aplicables if evaluacion.hit]

    por_categoria: dict[str, float] = {}
    for categoria in ("directa", "multi_pagina"):
        grupo = [e for e in aplicables if e.pregunta.categoria == categoria]
        if grupo:
            por_categoria[categoria] = sum(1 for e in grupo if e.hit) / len(grupo)

    posiciones = [e.posicion for e in hits if e.posicion is not None]
    coberturas = [e.cobertura for e in evaluaciones if e.cobertura is not None]
    sin_respuesta = [e for e in evaluaciones if e.pregunta.categoria == "sin_respuesta"]
    scores_max = tuple(max(e.scores) if e.scores else 0.0 for e in sin_respuesta)

    return Resumen(
        total=len(evaluaciones),
        aplicables=len(aplicables),
        hits=len(hits),
        hit_at_k=(len(hits) / len(aplicables)) if aplicables else None,
        hit_at_k_por_categoria=por_categoria,
        posicion_media=(sum(posiciones) / len(posiciones)) if posiciones else None,
        cobertura_media=(sum(coberturas) / len(coberturas)) if coberturas else None,
        scores_max_sin_respuesta=scores_max,
    )


def comprobar_fallback(buscar: BuscarFragmentos, llm: LLM) -> ResultadoFallback:
    """Verifica el fallback sin evidencia con retrieval real que devuelve 0 filas."""
    contador = LlmContador(llm)
    preguntar = Preguntar(buscar=buscar, llm=contador)
    respuesta = preguntar.ejecutar(PREGUNTA_DE_CONTROL, k=K_POR_DEFECTO, curso=CURSO_SIN_RESULTADOS)

    fuentes = tuple((fuente.documento, fuente.curso, fuente.pagina) for fuente in respuesta.fuentes)
    correcto = (
        respuesta.respuesta == MENSAJE_SIN_EVIDENCIA
        and not respuesta.fuentes
        and contador.llamadas == 0
    )
    return ResultadoFallback(
        respuesta=respuesta.respuesta,
        fuentes=fuentes,
        llamadas_llm=contador.llamadas,
        correcto=correcto,
    )


def _porcentaje(valor: float | None) -> str:
    return "n/a" if valor is None else f"{valor * 100:.1f} %"


def _decimal(valor: float | None) -> str:
    return "n/a" if valor is None else f"{valor:.4f}"


def construir_informe(
    *,
    ruta_dataset: str,
    k: int,
    evaluaciones: list[EvaluacionPregunta],
    resumen: Resumen,
    respuestas: dict[str, RespuestaRAG],
    comparativas: dict[str, list[ResultadoBusqueda]],
    fallback: ResultadoFallback,
) -> str:
    lineas: list[str] = []
    lineas.append(f"# Evaluación Fase 2 — {date.today().isoformat()}")
    lineas.append("")
    lineas.append(f"- Dataset: `{ruta_dataset}` ({resumen.total} preguntas).")
    lineas.append(f"- Baseline: `k = {k}`, sin _threshold_.")
    lineas.append("")
    lineas.append("## Resumen de retrieval")
    lineas.append("")
    lineas.append("| Métrica | Valor |")
    lineas.append("| --- | --- |")
    lineas.append(
        f"| Hit@{k} global | {_porcentaje(resumen.hit_at_k)} "
        f"({resumen.hits}/{resumen.aplicables}) |"
    )
    for categoria, valor in resumen.hit_at_k_por_categoria.items():
        lineas.append(f"| Hit@{k} · {categoria} | {_porcentaje(valor)} |")
    lineas.append(f"| Posición media del primer acierto | {_decimal(resumen.posicion_media)} |")
    lineas.append(f"| Cobertura media (multi-página) | {_porcentaje(resumen.cobertura_media)} |")
    lineas.append("")

    lineas.append(f"## Detalle de retrieval (filtro de curso, k = {k})")
    lineas.append("")
    lineas.append(
        "| ID | Categoría | Hit | Posición | Score 1er acierto | Scores top-k | "
        "Recuperado (documento · página) |"
    )
    lineas.append("| --- | --- | --- | --- | --- | --- | --- |")
    for evaluacion in evaluaciones:
        hit = "n/a" if evaluacion.hit is None else ("sí" if evaluacion.hit else "no")
        recuperado = ", ".join(
            f"{documento} · p.{pagina}" for documento, pagina in evaluacion.paginas_recuperadas
        )
        lineas.append(
            f"| {evaluacion.pregunta.id} | {evaluacion.pregunta.categoria} | {hit} | "
            f"{evaluacion.posicion if evaluacion.posicion is not None else 'n/a'} | "
            f"{_decimal(evaluacion.score_primer_acierto)} | "
            f"{', '.join(_decimal(score) for score in evaluacion.scores)} | {recuperado} |"
        )
    lineas.append("")

    lineas.append("## Comparativa top-k sin filtro de curso (dato, no métrica)")
    lineas.append("")
    lineas.append("| ID | Top-k sin filtro (documento · página) |")
    lineas.append("| --- | --- |")
    for evaluacion in evaluaciones:
        resultados = comparativas.get(evaluacion.pregunta.id, [])
        texto = ", ".join(f"{r.documento} · p.{r.pagina}" for r in resultados) or "(sin resultados)"
        lineas.append(f"| {evaluacion.pregunta.id} | {texto} |")
    lineas.append("")

    lineas.append("## Comprobación de retrieval vacío (fallback)")
    lineas.append("")
    lineas.append(f"- Resultado: {'correcto' if fallback.correcto else 'INCORRECTO'}.")
    lineas.append(f"- Respuesta: {fallback.respuesta}")
    lineas.append(f"- Fuentes: {len(fallback.fuentes)}")
    lineas.append(f"- Llamadas al LLM generativo: {fallback.llamadas_llm}")
    lineas.append("")

    lineas.append("## Hoja de revisión de generación")
    lineas.append("")
    lineas.append(
        "Valorar cada respuesta: corrección, fidelidad al contexto, ausencia de invenciones, "
        "comportamiento ante preguntas sin respuesta (abstención) y correspondencia de fuentes."
    )
    lineas.append("")
    for evaluacion in evaluaciones:
        respuesta = respuestas.get(evaluacion.pregunta.id)
        lineas.append(f"### {evaluacion.pregunta.id} — {evaluacion.pregunta.pregunta}")
        lineas.append("")
        lineas.append(
            f"- Categoría: {evaluacion.pregunta.categoria} · Curso: {evaluacion.pregunta.curso}"
        )
        if evaluacion.pregunta.documento is not None:
            paginas = ", ".join(str(p) for p in evaluacion.pregunta.paginas_esperadas)
            lineas.append(
                f"- Documento esperado: {evaluacion.pregunta.documento} · páginas {paginas}"
            )
        lineas.append(f"- Respuesta de referencia: {evaluacion.pregunta.respuesta_referencia}")
        lineas.append(
            f"- Respuesta obtenida: {respuesta.respuesta if respuesta else '(sin respuesta)'}"
        )
        if respuesta and respuesta.fuentes:
            fuentes = "; ".join(
                f"{fuente.curso} · {fuente.documento} · p.{fuente.pagina}"
                for fuente in respuesta.fuentes
            )
        else:
            fuentes = "(ninguna)"
        lineas.append(f"- Fuentes: {fuentes}")
        abstencion = "n/a" if evaluacion.pregunta.categoria != "sin_respuesta" else ""
        lineas.append("")
        lineas.append("| Corrección | Fidelidad | Sin invenciones | Abstención | Fuentes |")
        lineas.append("| --- | --- | --- | --- | --- |")
        lineas.append(f"|  |  |  | {abstencion} |  |")
        lineas.append("")

    lineas.append("## Diagnóstico")
    lineas.append("")
    fallos_retrieval = [e.pregunta.id for e in evaluaciones if e.hit is not None and not e.hit]
    lineas.append("### Fallos de retrieval")
    lineas.append("")
    lineas.append(
        "Preguntas con hit = 0: " + (", ".join(fallos_retrieval) if fallos_retrieval else "ninguna")
    )
    lineas.append("")
    lineas.append("### Fallos de generación")
    lineas.append("")
    lineas.append(
        "Completar tras la valoración: respuesta incorrecta pese al contexto correcto, "
        "invención, abstención errónea o fuentes incorrectas."
    )
    lineas.append("")
    lineas.append("### Scores de preguntas sin respuesta (referencia para un futuro threshold)")
    lineas.append("")
    for evaluacion in evaluaciones:
        if evaluacion.pregunta.categoria != "sin_respuesta":
            continue
        maximo = max(evaluacion.scores) if evaluacion.scores else 0.0
        media = sum(evaluacion.scores) / len(evaluacion.scores) if evaluacion.scores else 0.0
        lineas.append(
            f"- {evaluacion.pregunta.id}: score máximo {_decimal(maximo)} · media {_decimal(media)}"
        )
    lineas.append("")
    return "\n".join(lineas)


def _construir() -> tuple[BuscarFragmentos, Preguntar, LLM]:
    from container import (
        cargar_configuracion,
        construir_buscar_fragmentos,
        construir_embedder_gemini,
        construir_llm_gemini,
        construir_preguntar,
        construir_vector_store,
    )

    configuracion = cargar_configuracion()
    faltantes = [
        nombre
        for nombre, valor in (
            ("DATABASE_URL", configuracion.database_url),
            ("GEMINI_API_KEY", configuracion.gemini_api_key),
        )
        if not valor
    ]
    if faltantes:
        raise FaltaConfiguracion(
            f"Faltan variables de entorno: {', '.join(faltantes)}. "
            "Usa `uv run --env-file .env python eval/evaluate.py`."
        )

    gemini_api_key = str(configuracion.gemini_api_key)
    embedder = construir_embedder_gemini(gemini_api_key)
    store = construir_vector_store(str(configuracion.database_url))
    buscar = construir_buscar_fragmentos(embedder=embedder, store=store)
    llm = construir_llm_gemini(gemini_api_key, modelo=configuracion.gemini_llm_model)
    preguntar = construir_preguntar(buscar=buscar, llm=llm)
    return buscar, preguntar, llm


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dataset", default="eval/dataset.json")
    parser.add_argument("--k", type=int, default=K_POR_DEFECTO)
    parser.add_argument("--resultados", default="eval/resultados")
    args = parser.parse_args(argv)

    if args.k < 1:
        print("Error: --k debe ser >= 1.", file=sys.stderr)
        return 2

    try:
        preguntas = cargar_dataset(args.dataset)
    except (DatasetInvalidoError, OSError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    try:
        buscar, preguntar, llm = _construir()
    except (FaltaConfiguracion, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    evaluaciones: list[EvaluacionPregunta] = []
    respuestas: dict[str, RespuestaRAG] = {}
    comparativas: dict[str, list[ResultadoBusqueda]] = {}

    from psycopg import Error as PsycopgError

    try:
        for pregunta in preguntas:
            print(f"[{pregunta.id}] {pregunta.pregunta}")
            resultados = buscar.ejecutar(pregunta.pregunta, k=args.k, curso=pregunta.curso)
            evaluacion = evaluar_pregunta(pregunta, resultados)
            evaluaciones.append(evaluacion)
            comparativas[pregunta.id] = buscar.ejecutar(pregunta.pregunta, k=args.k)
            respuestas[pregunta.id] = preguntar.ejecutar(
                pregunta.pregunta, k=args.k, curso=pregunta.curso
            )
            hit = "n/a" if evaluacion.hit is None else ("hit" if evaluacion.hit else "fallo")
            print(f"  [{hit}] posición={evaluacion.posicion} scores={evaluacion.scores}")

        fallback = comprobar_fallback(buscar, llm)
    except PsycopgError:
        print(
            "Error de PostgreSQL. Comprueba la conectividad de Supabase y la configuración; "
            "el detalle de conexión se omite para no exponer credenciales.",
            file=sys.stderr,
        )
        return 2
    except OSError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    resumen = resumir(evaluaciones)
    informe = construir_informe(
        ruta_dataset=args.dataset,
        k=args.k,
        evaluaciones=evaluaciones,
        resumen=resumen,
        respuestas=respuestas,
        comparativas=comparativas,
        fallback=fallback,
    )

    directorio = Path(args.resultados)
    directorio.mkdir(parents=True, exist_ok=True)
    destino = directorio / f"{date.today().isoformat()}.md"
    destino.write_text(informe, encoding="utf-8")

    print("")
    print(
        f"Hit@{args.k} global: {_porcentaje(resumen.hit_at_k)} "
        f"({resumen.hits}/{resumen.aplicables})"
    )
    print(f"Fallback sin evidencia: {'correcto' if fallback.correcto else 'INCORRECTO'}")
    print(f"Informe escrito en {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
