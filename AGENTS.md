# AGENTS.md — Nexo (asistente RAG de estudio sobre PDFs)

## Stack y estructura — Python ≥3.13, FastAPI y `uv`; un solo `pyproject.toml` raíz.

- `core/` alberga modelos, puertos y casos de uso; `adapters/`, sus integraciones. El núcleo de la Fase 0 está implementado y testeado; adaptadores e interfaces se añaden en sus fases. Supabase está en East US (Ohio).

## Comandos

- `uv sync` · `uv run pytest` · `uv run ruff check .` · `uv run ruff format --check .`
- Integración (solo con configuración y autorización): `uv run pytest -m integration`
- Aún no hay API, CLI `nexo` ni frontend ejecutables.

## Convenciones — Arquitectura hexagonal: el core depende de puertos, no de SDKs/adaptadores.

- Usa `uv` para Python; documentación y mensajes de usuario en español.
- `core/` solo importa la biblioteca estándar y `core.*` (lo verifica `tests/architecture`).
- `container.py` es el único composition root: configuración e inyección, sin clientes ni efectos al importar.

## Reglas de dominio / trampas conocidas

- `informe.md` es la fuente de verdad; propaga decisiones aprobadas a `roadmap.md` y al plan pertinente.
- `Fragmento` no contiene el embedding. `IngestarDocumento` filtra páginas con menos de 50 caracteres tras `strip()`; `PageChunker` no filtra.
- Baseline `k=4`, sin threshold: retrieval vacío → mensaje fijo, fuentes vacías y sin LLM; con resultados sí se llama al LLM.
- No cambiar `k`, el prompt ni el chunking sin comparar contra el baseline de la Fase 2.
- RLS habilitado, sin políticas para `anon`/`authenticated`, privilegios de tabla revocados a esos roles; backend/CLI usan PostgreSQL directo. No usar `FORCE RLS` ni exponer credenciales al frontend.

## Forma de trabajar 
- Antes de cambios no triviales, revisa informe, roadmap y plan actual; mantén cambios acotados. No hagas commits ni cambios en Supabase sin autorización explícita.
- Elimina archivos (scripts, tests, etc) temporales o de prueba que realices para no ensuciar el proyecto.

## Memoria

- Al empezar, lee `MEMORY.md` para conocer el estado del proyecto y las decisiones tomadas.
- Al terminar una tarea, actualízalo: estado actual, decisiones importantes (con su porqué) y errores a evitar.
- Mantenlo breve (máximo ~50 líneas): resume o elimina lo que ya no aporte.
- Si algo se convierte en una regla permanente, propón moverlo a `AGENTS.md` en lugar de dejarlo en la memoria.
- No guardes nunca datos sensibles (claves, tokens, datos personales).

## Límites

- ✅ Siempre: actualizar `MEMORY.md` al terminar cada tarea.
- ⚠️ Pregunta antes de añadir dependencias, cambiar contratos/esquema o realizar acciones externas con efectos.
- 🚫 Nunca incluyas secretos en archivos, logs, commits o respuestas.

## Verificación 
- Ejecuta `uv run pytest` y Ruff tras cambios Python; integración con `uv run pytest -m integration` solo con configuración y autorización. No afirmes que los tests pasan si no se ejecutaron.
