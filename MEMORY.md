# MEMORY.md — Nexo

Memoria vigente del proyecto. Mantenerla breve y actualizarla al terminar cada tarea.

## Estado actual

- MVP v1 en Fase 0 (Arquitectura + puertos); `informe.md` es el documento canónico.
- Existe el esqueleto de carpetas; `pyproject.toml`/`uv.lock` dejan Fase 0 sin dependencias de runtime y pytest/Ruff en desarrollo. Los módulos Python siguen vacíos.
- No hay casos de uso, adaptadores, `container.py`, API, CLI, frontend ni tests implementados.
- Python configurado en 3.13.7. Ruff pasa; `uv run pytest` aún no encuentra tests y sale con código 5.

## Decisiones (y por qué)

- El proyecto y su distribución se llaman `nexo`; el comando CLI previsto será `nexo`. Aún no hay CLI ejecutable.
- Arquitectura hexagonal; Supabase PostgreSQL + pgvector en East US (Ohio). Fase 0 cierra el core localmente; preparación/verificación de Supabase es un carril independiente no bloqueante, necesario antes de las integraciones de Fase 1.
- RLS habilitado en `documentos` y `fragmentos`, sin políticas para `anon`/`authenticated` y con sus privilegios de tabla revocados. Backend/CLI usarán `DATABASE_URL`; no `FORCE ROW LEVEL SECURITY`.
- Generación fija con `gemini-2.5-flash`; embeddings `gemini-embedding-2` de 768 dimensiones.
- Ingesta solo por CLI en el MVP. `IngestarDocumento` filtra páginas con menos de 50 caracteres tras `strip()`; `PageChunker` no filtra.
- `Fragmento` no incluye el embedding como campo de dominio; se persiste en BD y se pasa en paralelo. `Embedder` y `FakeEmbedder` usan 768 dimensiones; el fake produce valores sintéticos.
- Baseline de consulta: `k=4`, sin threshold. Solo cero resultados activa el mensaje fijo sin LLM; con resultados, llamar al LLM aunque el score sea bajo. El embedding de consulta se genera incluso si la búsqueda queda vacía.
- La evaluación medirá retrieval y generación por separado; el threshold es una mejora posterior, no una condición del baseline.
- En Fase 0, `container.py` limita configuración a variables de proceso e inyección explícita: sin `.env` obligatorio, clientes ni conexiones. Dependencias runtime se agregan por fase; `pydantic-settings` solo si se justifica.

## Aprendizajes y errores a evitar

- No documentar `uv run fastapi dev` ni `nexo ...` como utilizables todavía: faltan la app y el entry point. El nombre definitivo del proyecto y CLI es `nexo`.
- `.env` contiene secretos y está ignorado por Git; nunca leerlo, compartirlo ni guardar valores sensibles en documentación.

## Próximos pasos

- Implementar modelos, puertos, casos de uso y tests locales; fakes de embeddings con dimensión 768 y `container.py` sin conexiones.
- Preparar y verificar Supabase cuando haya `DATABASE_URL` y autorización; es un carril externo separado y no bloquea el cierre del core. No ejecutar cambios reales sin permiso.
- Antes de la integración de Fase 1, completar credenciales, revisar condiciones de embeddings/privacidad y verificar el esquema/RLS.
- Seguir `docs/plans/2026-10-04-fase-0-arquitectura-puertos.md` (plan de implementación convencional, reescrito el 2026-10-07); luego continuar según `roadmap.md`.
