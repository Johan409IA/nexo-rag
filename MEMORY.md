# MEMORY.md — Nexo

Memoria vigente del proyecto. Mantenerla breve y actualizarla al terminar cada tarea.

## Estado actual

- Fases 0 y 1 completadas; `informe.md` es la fuente de verdad.
- Fase 1 implementada y validada: hash e ingesta PDF, PyMuPDFLoader, PageChunker, GeminiEmbedder, PgVectorStore, composición y script auxiliar.
- Tests locales: `uv run pytest -q` = 83 passed, 12 deselected (integración); Ruff check y format limpios. `PgVectorStore` valida el resultado opcional de `RETURNING id`; Gemini valida respuestas nulas y convierte valores a `float`.
- Supabase: esquema aplicado; `uv run --env-file .env pytest -m integration -q --tb=no` = 12 passed. `SELECT 1` pasó y `SHOW ssl` confirmó `on`.
- Johan confirmó pruebas manuales correctas: extracción, ingesta, duplicado, retrieval y filtro de curso. Los residuos de tests se borraron y la suite limpia sus marcadores al finalizar.
- Pendiente: evaluación formal de retrieval (Fase 2), CLI formal (Fase 3), MCP, API y frontend.

## Decisiones (y por qué)

- El proyecto y su distribución se llaman `nexo`; el CLI formal se implementa en Fase 3. `scripts/prueba_fase1.py` es solo un auxiliar de pruebas manuales.
- Arquitectura hexagonal; Supabase PostgreSQL + pgvector en East US (Ohio). `PgVectorStore` abre una conexión por operación y registra el tipo vector con `search_path` que incluye `extensions`.
- RLS habilitado en `documentos` y `fragmentos`, sin políticas para `anon`/`authenticated` y con sus privilegios revocados. Backend/CLI usan `DATABASE_URL`; no `FORCE ROW LEVEL SECURITY`.
- Generación fija con `gemini-2.5-flash`; embeddings `gemini-embedding-2` de 768 dimensiones.
- Ingesta solo por CLI en el MVP. `IngestarDocumento` filtra páginas con menos de 50 caracteres tras `strip()`; `PageChunker` no filtra.
- `Fragmento` no incluye el embedding como campo de dominio; se persiste en BD y se pasa en paralelo. `Embedder` y `FakeEmbedder` usan 768 dimensiones; el fake produce valores sintéticos.
- Baseline de consulta: `k=4`, sin threshold. Solo cero resultados activa el mensaje fijo sin LLM; con resultados, llamar al LLM aunque el score sea bajo. El embedding de consulta se genera incluso si la búsqueda queda vacía.
- La evaluación medirá retrieval y generación por separado; el threshold es una mejora posterior, no una condición del baseline.
- En Fase 0, `container.py` limita configuración a variables de proceso e inyección explícita: sin `.env` obligatorio, clientes ni conexiones. Dependencias runtime se agregan por fase; `pydantic-settings` solo si se justifica.

## Aprendizajes y errores a evitar

- No documentar `uv run fastapi dev` ni `nexo ...` como comandos utilizables: faltan la app y el entry point formal.
- `.env` contiene secretos y está ignorado por Git; nunca leerlo, compartirlo ni guardar valores sensibles en documentación. Evitar imprimir excepciones que expongan la URL de PostgreSQL.

## Próximos pasos

- Continuar con la Fase 2: crear el dataset de evaluación y medir retrieval/generación por separado, manteniendo `k=4` y el chunking actual como baseline.
- Nunca copiar URL ni credenciales a logs/documentación; `.env` es local y está ignorado por Git.
