# Nexo — asistente de estudio sobre PDFs

Nexo es un proyecto educativo para construir un asistente RAG que responda preguntas sobre PDFs de clase con fuentes de curso, documento y página. El diseño contempla una CLI de ingesta/consulta, un servidor MCP, una API FastAPI y un chat web.

> **Estado:** MVP v1 en Fase 0 (Arquitectura + puertos). Por ahora el repositorio contiene el esqueleto de paquetes y la configuración Python; las funciones RAG y las interfaces aún no están implementadas.

## Requisitos

- Python 3.13 o posterior (`.python-version` fija 3.13.7).
- [`uv`](https://docs.astral.sh/uv/) para el entorno y las dependencias Python.
- Supabase y una API key de Gemini serán necesarios cuando se implementen los adaptadores reales.

## Instalación

Desde la raíz del repositorio:

```sh
uv sync
```

## Verificación disponible

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Ruff está configurado y sus dos comprobaciones pasan actualmente. Pytest también está configurado, pero todavía no hay pruebas implementadas: hoy recopila cero tests y termina con código 5. La Fase 0 añadirá tests del core con fakes; las pruebas reales de Supabase serán explícitas y requerirán configuración y autorización.

## Uso

Aún no hay un comando ejecutable para levantar el backend, la CLI o el frontend. `api/` no contiene todavía una aplicación FastAPI, `[project.scripts]` aún no registra `nexo` y `frontend/` no tiene un `package.json`. Los comandos previstos para fases posteriores son:

```text
nexo ingest <ruta-pdf> --curso "Nombre del curso"
nexo ask "pregunta" [--curso "Nombre del curso"]
```

No uses `uv run fastapi dev` como comando de arranque hasta que exista la aplicación y se documente su módulo.

## Diseño decidido para el MVP

- **Ingesta:** solo mediante CLI; detección de duplicados con SHA-256 del contenido. PyMuPDF extraerá texto por página. `IngestarDocumento` omitirá páginas cuyo texto, tras `strip()`, tenga menos de 50 caracteres y devolverá sus números; `PageChunker` no filtra y genera un fragmento por página recibida.
- **Embeddings y almacenamiento:** `gemini-embedding-2`, dimensión 768; PostgreSQL + pgvector en Supabase, región East US (Ohio). El vector se persiste en la base y no es un campo del modelo de dominio `Fragmento`.
- **Consulta:** recuperación inicial con `k=4`, sin threshold. Si no se recuperan filas, se devuelven fuentes vacías y el mensaje fijo `No encontré información suficiente en los apuntes disponibles para responder esta pregunta.` sin llamar al LLM generativo. Si hay fragmentos, se envían a `gemini-2.5-flash`, incluso si sus scores son bajos.
- **Seguridad:** RLS habilitado en `documentos` y `fragmentos`, sin políticas para `anon`/`authenticated` y con privilegios de tabla revocados a esos roles. Backend y CLI accederán por PostgreSQL directo usando `DATABASE_URL`; el frontend solo hablará con FastAPI. No se usará `FORCE ROW LEVEL SECURITY`.

Estas son decisiones del diseño; todavía no implican que los flujos estén implementados. Las claves y cadenas de conexión deben configurarse localmente y nunca incluirse en commits ni en el frontend.

## Configuración futura

Al integrar la base de datos y Gemini se prevén estas variables en el entorno privado del backend/CLI:

- `DATABASE_URL`
- `GEMINI_API_KEY`
- `GEMINI_LLM_MODEL=gemini-2.5-flash`

El valor del modelo generativo queda fijo durante el MVP; no es un selector de producto. No compartas valores secretos en el chat ni los publiques en archivos versionados.

## Documentación del proyecto

- Fuente de verdad y diseño: [`informe.md`](informe.md)
- Secuencia de fases: [`roadmap.md`](roadmap.md)
- Plan de Fase 0: [`docs/plans/2026-10-04-fase-0-arquitectura-puertos.md`](docs/plans/2026-10-04-fase-0-arquitectura-puertos.md)
- Instrucciones para agentes: [`AGENTS.md`](AGENTS.md)
- Estado y decisiones entre sesiones: [`MEMORY.md`](MEMORY.md)
