"""Pruebas manuales de la Fase 1: ingesta y retrieval contra los servicios reales.

Uso (desde la raíz del proyecto; `--env-file .env` carga DATABASE_URL y
GEMINI_API_KEY sin exponerlos):

    uv run --env-file .env python scripts/prueba_fase1.py muestra "<ruta.pdf>"
    uv run --env-file .env python scripts/prueba_fase1.py ingesta "<ruta.pdf>" --curso "..."
    uv run --env-file .env python scripts/prueba_fase1.py reingesta "<ruta.pdf>" --curso "..."
    uv run --env-file .env python scripts/prueba_fase1.py consultas
    uv run --env-file .env python scripts/prueba_fase1.py filtro --curso "..." --consulta "..."

Códigos de salida: 0 correcto, 1 documento duplicado, 2 configuración o uso.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psycopg import Error as PsycopgError

from container import (
    cargar_configuracion,
    construir_buscar_fragmentos,
    construir_chunker,
    construir_embedder_gemini,
    construir_ingestar,
    construir_loader_pdf,
    construir_vector_store,
)
from core.use_cases.buscar_fragmentos import BuscarFragmentos
from core.use_cases.ingestar_documento import DocumentoDuplicadoError

CONSULTAS_DE_PRUEBA = [
    "¿Qué es la escalabilidad horizontal?",
    "¿Qué es el big data y qué características tiene?",
    "¿Qué es la integración de sistemas de información?",
    "¿Qué protocolos o estándares se usan para integrar sistemas?",
    "¿Qué es una auditoría de seguridad?",
    "¿Qué controles de seguridad se aplican en un sistema de información?",
    "¿Qué es la confidencialidad de la información?",
    "¿Qué riesgos tiene una mala configuración de seguridad?",
]


def _credenciales() -> tuple[str, str]:
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
        raise SystemExit(
            f"Faltan variables de entorno: {', '.join(faltantes)}. "
            "Usa `uv run --env-file .env python scripts/prueba_fase1.py ...`."
        )
    return str(configuracion.database_url), str(configuracion.gemini_api_key)


def _buscar() -> BuscarFragmentos:
    database_url, gemini_api_key = _credenciales()
    return construir_buscar_fragmentos(
        embedder=construir_embedder_gemini(gemini_api_key),
        store=construir_vector_store(database_url),
    )


def cmd_muestra(ruta: str) -> int:
    paginas = construir_loader_pdf().leer(ruta)
    print(f"{ruta}: {len(paginas)} páginas")
    for numero, texto in paginas:
        print(f"  p.{numero} ({len(texto)} caracteres): {texto[:200]!r}")
    return 0


def cmd_ingesta(ruta: str, curso: str) -> int:
    database_url, gemini_api_key = _credenciales()
    caso = construir_ingestar(
        loader=construir_loader_pdf(),
        chunker=construir_chunker(),
        embedder=construir_embedder_gemini(gemini_api_key),
        store=construir_vector_store(database_url),
    )

    try:
        resultado = caso.ejecutar(ruta, curso)
    except DocumentoDuplicadoError:
        print("RECHAZADO: el documento ya fue ingestado (hash duplicado).")
        return 1

    total_paginas = len(construir_loader_pdf().leer(ruta))
    fragmentos = total_paginas - len(resultado.paginas_omitidas)
    print(f"Documento ingestado: {resultado.documento.nombre}")
    print(f"  curso:     {resultado.documento.curso}")
    print(f"  hash:      {resultado.documento.hash_sha256}")
    print(f"  fragmentos: {fragmentos} (de {total_paginas} páginas)")
    if resultado.paginas_omitidas:
        print(
            f"  Advertencia: {len(resultado.paginas_omitidas)} páginas omitidas "
            f"por contener muy poco texto: {resultado.paginas_omitidas}"
        )
    else:
        print("  Sin páginas omitidas.")
    return 0


def cmd_consultas() -> int:
    buscar = _buscar()
    for consulta in CONSULTAS_DE_PRUEBA:
        print(f"\nConsulta: {consulta}")
        resultados = buscar.ejecutar(consulta)
        if not resultados:
            print("  (sin resultados)")
            continue
        for resultado in resultados:
            print(
                f"  score={resultado.score:.4f} · {resultado.curso} · "
                f"{resultado.documento} · p.{resultado.pagina}"
            )
            print(f"    {resultado.texto[:120]}...")
    return 0


def cmd_filtro(curso: str, consulta: str) -> int:
    buscar = _buscar()
    print(f"Consulta: {consulta} (curso: {curso})")
    resultados = buscar.ejecutar(consulta, curso=curso)
    if not resultados:
        print("  (sin resultados)")
        return 0
    for resultado in resultados:
        print(
            f"  score={resultado.score:.4f} · {resultado.curso} · "
            f"{resultado.documento} · p.{resultado.pagina}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    muestra = subcomandos.add_parser("muestra", help="muestra el texto extraído de un PDF")
    muestra.add_argument("ruta")

    for nombre, ayuda in (
        ("ingesta", "ingiere un PDF"),
        ("reingesta", "reintenta la ingesta; debe rechazarse por duplicado"),
    ):
        sub = subcomandos.add_parser(nombre, help=ayuda)
        sub.add_argument("ruta")
        sub.add_argument("--curso", required=True)

    subcomandos.add_parser("consultas", help="lanza consultas de prueba con scores")

    filtro = subcomandos.add_parser("filtro", help="busca filtrando por curso")
    filtro.add_argument("--curso", required=True)
    filtro.add_argument("--consulta", required=True)

    args = parser.parse_args(argv)

    try:
        if args.comando == "muestra":
            return cmd_muestra(args.ruta)
        if args.comando in ("ingesta", "reingesta"):
            return cmd_ingesta(args.ruta, args.curso)
        if args.comando == "consultas":
            return cmd_consultas()
        return cmd_filtro(args.curso, args.consulta)
    except (FileNotFoundError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except PsycopgError as error:
        print(
            f"Error de PostgreSQL ({type(error).__name__}). "
            "Comprueba la conectividad de Supabase y la configuración; "
            "el detalle de conexión se omite para no exponer credenciales.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
