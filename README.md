# Nexo — asistente de estudio sobre PDFs

Nexo es un proyecto educativo para construir un asistente RAG que responda preguntas sobre PDFs de clase con fuentes de curso, documento y página. El diseño contempla una CLI de ingesta/consulta, un servidor MCP, una API FastAPI y un chat web.

> **Estado:** Fases 0 y 1 completadas. La ingesta PDF y el retrieval con Gemini y Supabase están implementados y verificados con tests locales, integración remota y pruebas manuales. La evaluación formal del retrieval corresponde a la Fase 2; el CLI formal, MCP, API y frontend siguen pendientes.

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
- **Retrieval:** búsqueda por similitud con `k=4`, sin threshold y con filtro opcional por curso; devuelve fragmentos, fuentes y scores. `Preguntar` en el core define el fallback sin evidencia y el puerto LLM, pero el adaptador generativo Gemini y la evaluación formal corresponden a fases posteriores.
- **Seguridad:** RLS está habilitado en `documentos` y `fragmentos`, sin políticas para `anon`/`authenticated` y con privilegios revocados a esos roles. El backend usa PostgreSQL directo mediante `DATABASE_URL`; el frontend previsto hablará con FastAPI. No se usa `FORCE ROW LEVEL SECURITY`.

La Fase 1 está implementada y verificada. Guarda las credenciales solo en `.env` local (ignorado por Git); nunca las incluyas en commits ni en el frontend.

## Configuración

El script de pruebas manuales usa estas variables del entorno privado:

- `DATABASE_URL`
- `GEMINI_API_KEY`

Estas variables las necesita el script de pruebas manuales. `GEMINI_LLM_MODEL` se reservará para la integración generativa posterior. No compartas valores secretos en el chat ni los publiques en archivos versionados.

## Documentación del proyecto

- Fuente de verdad y diseño: [`informe.md`](informe.md)
- Secuencia de fases: [`roadmap.md`](roadmap.md)
- Plan de Fase 0: [`docs/plans/2026-10-04-fase-0-arquitectura-puertos.md`](docs/plans/2026-10-04-fase-0-arquitectura-puertos.md)
- Plan de Fase 1: [`docs/plans/2026-10-08-fase-1-ingesta-retrieval.md`](docs/plans/2026-10-08-fase-1-ingesta-retrieval.md)
- Registro de cambios: [`CHANGELOG.md`](CHANGELOG.md)
- Instrucciones para agentes: [`AGENTS.md`](AGENTS.md)
- Estado y decisiones entre sesiones: [`MEMORY.md`](MEMORY.md)
