# MEMORY.md — Nexo

Memoria vigente del proyecto. Mantenerla breve y actualizarla al terminar cada tarea.

## Estado actual

- Fases 0 y 1 completadas; `informe.md` es la fuente de verdad.
- Fase 1 implementada y validada: hash e ingesta PDF, PyMuPDFLoader, PageChunker, GeminiEmbedder, PgVectorStore, composición y script auxiliar.
- Tests locales: `uv run pytest -q` = 106 passed, 2 skipped (integración sin credenciales); Ruff check y format limpios. `PgVectorStore` valida el resultado opcional de `RETURNING id`; Gemini valida respuestas nulas y convierte valores a `float`.
- Supabase: esquema aplicado; `uv run --env-file .env pytest -m integration -q --tb=no` = 12 passed. `SELECT 1` pasó y `SHOW ssl` confirmó `on`.
- Johan confirmó pruebas manuales correctas: extracción, ingesta, duplicado, retrieval y filtro de curso. Los residuos de tests se borraron y la suite limpia sus marcadores al finalizar.
- Fase 2 completada: `GeminiLLM` (reintentos 429/503), `construir_llm_gemini`, `eval/dataset.json` (18 preguntas) y `eval/evaluate.py`; informe con valoración en `eval/resultados/2026-10-13.md`.
- Baseline medido (k=4, sin threshold, run con `gemini-3.5-flash-lite`): Hit@4 = 100 % (13/13) con posición 1 en todos y cobertura multi-página 100 %; fallback correcto sin llamadas al LLM; generación sin invenciones y abstención correcta (5/5). Threshold candidato ~0.62–0.73 queda para la Fase 8.
- Fase 2 cerrada: documentación actualizada (README, CHANGELOG, informe, roadmap). Pendientes: CLI (Fase 3), MCP, API y frontend.

## Decisiones (y por qué)

- El proyecto y su distribución se llaman `nexo`; el CLI formal se implementa en Fase 3. `scripts/prueba_fase1.py` es solo un auxiliar de pruebas manuales.
- Arquitectura hexagonal; Supabase PostgreSQL + pgvector en East US (Ohio). `PgVectorStore` abre una conexión por operación y registra el tipo vector con `search_path` que incluye `extensions`.
- RLS habilitado en `documentos` y `fragmentos`, sin políticas para `anon`/`authenticated` y con sus privilegios revocados. Backend/CLI usan `DATABASE_URL`; no `FORCE ROW LEVEL SECURITY`.
- Generación fija con `gemini-3.5-flash-lite` (2026-10-14: `gemini-2.5-flash` ya no se ofrece a usuarios nuevos y `gemini-3.8-flash` solo permite 20 peticiones/día; aprobado el lite por sus 500/día y es el modelo con el que se midió el baseline); embeddings `gemini-embedding-2` de 768 dimensiones. `GEMINI_LLM_MODEL` en `.env` debe valer `gemini-3.5-flash-lite`.
- Ingesta solo por CLI en el MVP. `IngestarDocumento` filtra páginas con menos de 50 caracteres tras `strip()`; `PageChunker` no filtra.
- `Fragmento` no incluye el embedding como campo de dominio; se persiste en BD y se pasa en paralelo. `Embedder` y `FakeEmbedder` usan 768 dimensiones; el fake produce valores sintéticos.
- Baseline de consulta: `k=4`, sin threshold. Solo cero resultados activa el mensaje fijo sin LLM; con resultados, llamar al LLM aunque el score sea bajo. El embedding de consulta se genera incluso si la búsqueda queda vacía.
- La evaluación medirá retrieval y generación por separado; el threshold es una mejora posterior, no una condición del baseline.
- En Fase 0, `container.py` limita configuración a variables de proceso e inyección explícita: sin `.env` obligatorio, clientes ni conexiones. Dependencias runtime se agregan por fase; `pydantic-settings` solo si se justifica.

## Aprendizajes y errores a evitar

- No documentar `uv run fastapi dev` ni `nexo ...` como comandos utilizables: faltan la app y el entry point formal.
- `.env` contiene secretos y está ignorado por Git; nunca leerlo, compartirlo ni guardar valores sensibles en documentación. Evitar imprimir excepciones que expongan la URL de PostgreSQL.
- Gemini falla con 503 «alta demanda» de forma intermitente: `GeminiLLM` reintenta (2–32 s); si el run completo de `evaluate.py` no termina, esperar y relanzar. No cambiar k/prompt/chunking por eso.
- El catálogo `client.models.list()` puede listar modelos que la clave ya no puede usar: validar con una llamada real antes de asumir disponibilidad.

## Próximos pasos

- Johan revisa la valoración de generación de `eval/resultados/2026-10-13.md`; al cerrar la Fase 2, actualizar README/CHANGELOG (skill project-docs).
- Continuar con la Fase 3: CLI `nexo ingest` y `nexo ask`.
- Nunca copiar URL ni credenciales a logs/documentación; `.env` es local y está ignorado por Git.
