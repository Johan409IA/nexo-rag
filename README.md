# Nexo — asistente de estudio sobre PDFs

Nexo es un proyecto educativo para construir un asistente RAG que responda preguntas sobre PDFs de clase con fuentes de curso, documento y página. El diseño contempla una CLI de ingesta/consulta, un servidor MCP, una API FastAPI y un chat web.

> **Estado:** Fases 0, 1 y 2 completadas. La ingesta PDF, el retrieval y el baseline de evaluación (retrieval y generación) están implementados y verificados con tests locales, integración remota, pruebas manuales y la evaluación documentada. Siguientes fases: CLI formal (3), MCP (4), API (5) y frontend (6).

## Requisitos

- Python 3.13 o posterior (`.python-version` fija 3.13.7).
- [`uv`](https://docs.astral.sh/uv/) para el entorno y las dependencias Python.
- Para ejecutar las pruebas manuales de Fase 1: acceso a Supabase PostgreSQL, `DATABASE_URL` con SSL (`sslmode=require`) y `GEMINI_API_KEY`.

## Instalación

Desde la raíz del repositorio:

```sh
uv sync
```

## Verificación

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Los tests locales usan fakes y no necesitan red ni credenciales. Para verificar la integración con Supabase de forma explícita, ejecuta `uv run --env-file .env pytest -m integration`; requiere conectividad y una `DATABASE_URL` vigente. La integración de Fase 1 se verificó con 12 tests aprobados. No compartas `.env` ni sus valores.

## Pruebas manuales de Fase 1

El script auxiliar permite inspeccionar extracción, ingestar PDFs y comprobar retrieval. No es el CLI formal `nexo`.

```powershell
$docs = "C:\Users\<usuario>\Downloads\Documentos"
uv run --env-file .env python scripts/prueba_fase1.py muestra "$docs\S07_s1 Escalabilidad y big data.pdf"
uv run --env-file .env python scripts/prueba_fase1.py ingesta "$docs\S07_s1 Escalabilidad y big data.pdf" --curso "Escalabilidad y big data"
uv run --env-file .env python scripts/prueba_fase1.py consultas
uv run --env-file .env python scripts/prueba_fase1.py filtro --curso "Escalabilidad y big data" --consulta "¿Qué es la escalabilidad horizontal?"
```

Repite `ingesta` con el mismo PDF para verificar que el duplicado se rechaza. Para los otros PDFs, usa el nombre de curso correspondiente: `Integración de sistemas de información` o `Seguridad, auditoría`. Las pruebas manuales confirmaron extracción, ingesta, rechazo de duplicados, retrieval y filtro por curso.

Configura localmente `DATABASE_URL` y `GEMINI_API_KEY` en `.env`; `DATABASE_URL` debe usar `sslmode=require`. No guardes credenciales en documentación ni en el repositorio.

## Evaluación (Fase 2)

`eval/evaluate.py` ejecuta el dataset de 18 preguntas (`eval/dataset.json`) contra los servicios reales: métricas de retrieval (Hit@k, posición, scores, cobertura multi-página), comparativa sin filtro de curso, comprobación del fallback sin evidencia (mensaje fijo y cero llamadas al LLM) y hoja de revisión de generación. El informe se escribe en `eval/resultados/<fecha>.md`.

```powershell
uv run --env-file .env python eval/evaluate.py
```

Consume cuota de Gemini (embedding de consulta por pregunta y llamada al LLM generativo por pregunta con resultados). El baseline medido con `k = 4` y sin threshold: Hit@4 = 100 % (13/13) con posición 1 en todos los casos, fallback correcto y generación sin invenciones; ver [`eval/resultados/2026-10-13.md`](eval/resultados/2026-10-13.md). No cambies `k`, el prompt ni el chunking sin comparar contra este baseline.

## Uso

Aún no hay un comando ejecutable para levantar el backend, la CLI o el frontend. `api/` no contiene todavía una aplicación FastAPI, `[project.scripts]` aún no registra `nexo` y `frontend/` no tiene un `package.json`. Los comandos previstos para fases posteriores son:

```text
nexo ingest <ruta-pdf> --curso "Nombre del curso"
nexo ask "pregunta" [--curso "Nombre del curso"]
```

No uses `uv run fastapi dev` como comando de arranque hasta que exista la aplicación y se documente su módulo.

## Diseño decidido para el MVP

- **Ingesta:** el flujo implementado calcula SHA-256 del contenido para detectar duplicados; PyMuPDF extrae texto por página. `IngestarDocumento` omite páginas con menos de 50 caracteres tras `strip()` y reporta sus números; `PageChunker` no filtra y genera un fragmento por página recibida. La verificación actual usa `scripts/prueba_fase1.py`; el CLI formal está previsto para la Fase 3.
- **Embeddings y almacenamiento:** `GeminiEmbedder` usa `gemini-embedding-2` con vectores de 768 dimensiones; `PgVectorStore` persiste en PostgreSQL + pgvector en Supabase (East US, Ohio). El vector no es campo del modelo de dominio `Fragmento`.
- **Retrieval y generación:** búsqueda por similitud con `k=4`, sin threshold y con filtro opcional por curso; devuelve fragmentos, fuentes y scores. Con retrieval vacío, `Preguntar` devuelve el mensaje fijo sin llamar al LLM; con resultados, responde `GeminiLLM` con el modelo fijo `gemini-3.5-flash-lite` (reintentos ante 429/503) y fuentes deduplicadas en orden estable. La evaluación formal vive en `eval/`.
- **Seguridad:** RLS está habilitado en `documentos` y `fragmentos`, sin políticas para `anon`/`authenticated` y con privilegios revocados a esos roles. El backend usa PostgreSQL directo mediante `DATABASE_URL`; el frontend previsto hablará con FastAPI. No se usa `FORCE ROW LEVEL SECURITY`.

Las Fases 0–2 están implementadas y verificadas. Guarda las credenciales solo en `.env` local (ignorado por Git); nunca las incluyas en commits ni en el frontend.

## Configuración

El script de pruebas manuales y la evaluación usan estas variables del entorno privado:

- `DATABASE_URL`
- `GEMINI_API_KEY`
- `GEMINI_LLM_MODEL` (valor aprobado: `gemini-3.5-flash-lite`)

`GEMINI_LLM_MODEL` declara el modelo generativo fijo del MVP. No compartas valores secretos en el chat ni los publiques en archivos versionados.

## Documentación del proyecto

- Fuente de verdad y diseño: [`informe.md`](informe.md)
- Secuencia de fases: [`roadmap.md`](roadmap.md)
- Plan de Fase 0: [`docs/plans/2026-10-04-fase-0-arquitectura-puertos.md`](docs/plans/2026-10-04-fase-0-arquitectura-puertos.md)
- Plan de Fase 1: [`docs/plans/2026-10-08-fase-1-ingesta-retrieval.md`](docs/plans/2026-10-08-fase-1-ingesta-retrieval.md)
- Plan de Fase 2: [`docs/plans/2026-10-14-fase-2-evaluacion.md`](docs/plans/2026-10-14-fase-2-evaluacion.md)
- Registro de cambios: [`CHANGELOG.md`](CHANGELOG.md)
- Instrucciones para agentes: [`AGENTS.md`](AGENTS.md)
- Estado y decisiones entre sesiones: [`MEMORY.md`](MEMORY.md)
