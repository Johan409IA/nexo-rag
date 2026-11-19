# Fase 2: Evaluación — GeminiLLM, dataset, Hit@k y baseline de retrieval + generación

## Objetivo

Cumplir las 6 tareas de la Fase 2 de `roadmap.md` y la sección 17 de `informe.md`: fijar un baseline medido de retrieval (`Hit@k` con `k = 4`, sin _threshold_) y evaluar la generación de forma manual o semiautomática, antes de construir más interfaces.

## Contexto

- Fases 0 y 1 completadas. Existen: `BuscarFragmentos`, `Preguntar`, `IngestarDocumento`, adaptadores `PyMuPDFLoader`, `PageChunker`, `GeminiEmbedder`, `PgVectorStore` y `container.py` con sus fábricas.
- `eval/` está vacío (solo `.gitkeep`).
- **Hueco:** no existe el adaptador `GeminiLLM` ni su fábrica; el puerto `LLM` solo se satisface con `FakeLLM` (de `tests/fakes/`). Sin él, la tarea 5 del roadmap (evaluar la generación) es imposible. `container.py` ya tiene `GEMINI_LLM_MODEL_POR_DEFECTO = "gemini-2.5-flash"` y `Configuracion.gemini_llm_model` sin consumidor.
- Corpus disponible (PDFs de prueba de la Fase 1, en `C:\Users\Johan Castillon\Downloads\Documentos`):
  - `S07_s1 Escalabilidad y big data.pdf` (curso «Escalabilidad y big data»)
  - `S08_s1 Integración de sistemas de información.pdf` (curso «Integración de sistemas de información»)
  - `S09_s1 Seguridad, auditoría.pdf` (curso «Seguridad, auditoría»)
- Punto de composición de referencia: `scripts/prueba_fase1.py` (usa `cargar_configuracion()` y las fábricas de `container.py`; se ejecuta con `uv run --env-file .env`).
- `tests/architecture/test_dependencias.py` solo restringe `core/`, `adapters/` y los paquetes de interfaz (`api`, `cli`, `mcp_server`). `eval/` puede importar `container` y `core.*`; no debe importar `adapters` directamente.

## Alcance

**Incluido (las 6 tareas del roadmap + el habilitador):**

1. Adaptador `GeminiLLM` + fábrica en `container.py` + tests (habilitador de la tarea 5).
2. Corpus de 3 PDFs verificado/ingestado en Supabase (tarea 1).
3. `eval/dataset.json` con 15–20+ preguntas redactadas por el agente (tarea 2).
4. `eval/evaluate.py`: métricas de retrieval (`Hit@k`, posición, scores, cobertura multi-página) (tarea 3) + comprobación del fallback de retrieval vacío (tarea 4).
5. Evaluación de generación manual/semiautomática sobre las respuestas reales de `Preguntar` (tarea 5).
6. Resultados en `eval/resultados/AAAA-MM-DD.md` con diagnóstico que separa fallos de retrieval y de generación (tarea 6).
7. Tests unitarios de métricas y del adaptador (sin red, sin servicios).
8. Archivo del plan en `docs/plans/`, sincronización de `informe.md`/`roadmap.md` y actualización de `MEMORY.md`.

**Fuera de alcance:**

- Cambiar `k`, el prompt ni el chunking (prohibido sin comparar contra este baseline — regla del roadmap).
- CLI formal (Fase 3) — `evaluate.py` es un script de `eval/`, no un comando `nexo`. El cableado de `GeminiLLM` en CLI/API/MCP pertenece a las fases 3–5 y no se adelanta.
- Cambios de esquema en Supabase ni nuevas dependencias (`google-genai` y `psycopg` ya están instaladas por la Fase 1).

## Decisiones

1. **`GeminiLLM` implementa el puerto `LLM`** (`responder(prompt: str) -> str`) con el SDK `google-genai` ya instalado, siguiendo el patrón de `adapters/ai/gemini_embedder.py` (`genai.Client(api_key=...)`). Modelo configurable por constructor con fallback a `GEMINI_LLM_MODEL_POR_DEFECTO` (`gemini-2.5-flash`, fijo durante el MVP). Durante la implementación, verificar la firma exacta del método de generación del SDK contra la versión instalada (ctx7 / documentación oficial) — no inventar la API.
2. **Fábrica `construir_llm_gemini(gemini_api_key: str, modelo: str | None = None) -> GeminiLLM`** en `container.py`, consumiendo `Configuracion.gemini_llm_model` como valor de entrada. Mismo estilo que `construir_embedder_gemini`.
3. **Dataset — esquema por pregunta** (decisión del usuario: números de página + un documento por pregunta):
   ```json
   {
     "id": "P01",
     "pregunta": "¿Qué es la escalabilidad horizontal?",
     "curso": "Escalabilidad y big data",
     "categoria": "directa",
     "documento": "S07_s1 Escalabilidad y big data.pdf",
     "paginas_esperadas": [3],
     "respuesta_referencia": "..."
   }
   ```
   - `categoria` ∈ `{"directa", "multi_pagina", "sin_respuesta"}`.
   - `documento` y `paginas_esperadas` se omiten (o van `null`/`[]`) en `sin_respuesta`; en las demás categorías `documento` es obligatorio y `paginas_esperadas` tiene ≥ 1 página válida (≥ 1, no omitida por el filtro de 50 caracteres).
   - Limitación aceptada: preguntas cuya respuesta esté en varios documentos quedan fuera del dataset.
4. **Métricas de retrieval** (baseline `k = 4`, `BuscarFragmentos.K_POR_DEFECTO`):
   - `Hit@4`: 1 si algún resultado del top-4 es del `documento` esperado con `pagina` ∈ `paginas_esperadas`; 0 en caso contrario. No aplica a `sin_respuesta`.
   - `posicion`: posición 1-based del primer acierto; `null` si no hay.
   - `cobertura` (solo `multi_pagina`): páginas esperadas recuperadas / páginas esperadas.
   - `scores`: score del primer acierto y lista de scores del top-4.
   - `sin_respuesta`: sin Hit; se reportan scores (máximo y promedio del top-4) como referencia para un futuro threshold.
   - Agregados: `Hit@4` global y por categoría, posición media de los aciertos.
5. **Consulta con filtro de curso**: cada pregunta se ejecuta con `curso=curso` del dataset (uso real con selector de curso). Se registra también el top-4 sin filtro en el informe como dato comparativo, sin entrar en las métricas del baseline.
6. **Comprobación de retrieval vacío** (tarea 4) contra servicios reales: `Preguntar` con filtro `curso` inexistente devuelve 0 filas; envolviendo el `GeminiLLM` real en un contador (clase en `eval/` que implementa el puerto `LLM`, delega y cuenta llamadas) se comprueba `respuesta == MENSAJE_SIN_EVIDENCIA`, `fuentes == []` y **cero llamadas al LLM**. El embedding de consulta sí se genera y consume cuota (como manda el informe). El test unitario equivalente usa `FakeLLM` + `InMemoryVectorStore` vacío.
7. **Evaluación de generación semiautomática** (tarea 5, criterios del informe §17.2): para cada pregunta se ejecuta `Preguntar` real y se vuelca una hoja de revisión con `respuesta_referencia`, respuesta obtenida y fuentes. Criterios de valoración por pregunta:
   - corrección de la respuesta;
   - fidelidad al contexto recuperado;
   - ausencia de afirmaciones no respaldadas (invenciones);
   - comportamiento ante `sin_respuesta` (el LLM debe indicar falta de evidencia — en el baseline hay resultados y sí se llama al LLM);
   - correspondencia de las fuentes.
   El agente realiza la primera pasada de valoración anclándose a `respuesta_referencia` y al contexto; el usuario la revisa y ajusta. La valoración no se automatiza con otro LLM.
8. **`eval/evaluate.py` se compone solo con `container.py` y `core.*`**, nunca importa `adapters` directamente. Los imports de `container` van dentro de las funciones de composición (lazy), para que las métricas puras sean testeables sin dependencias de runtime.
9. **Ejecución con credenciales**: `uv run --env-file .env python eval/evaluate.py ...` (patrón de `scripts/prueba_fase1.py`). El agente nunca lee, imprime ni documenta valores de `.env`; las excepciones de psycopg no deben exponer la URL de conexión.

## Tareas

1. **Implementar `adapters/ai/gemini_llm.py`** (`GeminiLLM`): `responder(prompt: str) -> str` con el SDK `google-genai` (patrón de `gemini_embedder.py`), modelo por constructor con fallback a `gemini-2.5-flash`, manejo defensivo de respuestas nulas/vacías del SDK (mismo criterio que `GeminiEmbedder`). Verificar la firma real del SDK con la versión instalada antes de escribir el código.
2. **Añadir `construir_llm_gemini` a `container.py`** (decisión 2) y completar `tests/test_container.py`: fábrica construida, modelo por defecto y `repr` sin secretos.
3. **Tests del adaptador** en `tests/adapters/ai/test_gemini_llm.py` con cliente simulado (patrón de `tests/adapters/ai/test_gemini_embedder.py`): prompt reenviado, modelo usado, respuesta nula/vacía manejada, `responder` devuelve `str`.
4. **Extraer el texto del corpus para redactar preguntas.** Script temporal en el scratchpad (no en el repo) que use `construir_loader_pdf().leer(ruta)` sobre los 3 PDFs y vuelque el texto por página a ficheros del scratchpad. No consume cuota de Gemini. Borrar el script al terminar. Comprobar también las páginas omitidas (< 50 caracteres tras `strip()`): no se referenciarán en `paginas_esperadas`.
5. **Redactar `eval/dataset.json`.** 15–20+ preguntas ancladas al texto extraído (cada `pagina_esperada` debe corresponderse con el contenido real de esa página; verificarlo contra el volcado del paso 4):
   - 7–8 `directa`, 5–6 `multi_pagina`, 4–5 `sin_respuesta`.
   - Las `sin_respuesta` tratan temas ajenos a los 3 documentos (sin `documento` ni `paginas_esperadas`).
   - Incluir `respuesta_referencia` en todas (en `sin_respuesta`, la respuesta correcta es declarar falta de evidencia).
   - IDs correlativos (`P01`, `P02`, …).
6. **Implementar `eval/evaluate.py`** con:
   - Carga y validación del dataset (campos requeridos, categorías válidas, páginas ≥ 1, coherencia `sin_respuesta`); error claro con el id de la pregunta inválida.
   - Funciones puras de métricas (`calcular_hit`, `calcular_posicion`, `calcular_cobertura`, `evaluar_pregunta`, `resumir`) con `dataclass` de resultado.
   - Runner `main()` (argparse): `--dataset` (por defecto `eval/dataset.json`), `--k` (por defecto 4), `--resultados` (por defecto `eval/resultados/`); compone `BuscarFragmentos` y `Preguntar` reales; por cada pregunta: retrieval con filtro de curso (más top-4 sin filtro como dato) y generación con `Preguntar` (decisión 5).
   - Comprobación de fallback de la decisión 6 (contador de llamadas al LLM sobre el `GeminiLLM` real).
   - Escritura de `eval/resultados/<AAAA-MM-DD>.md` (crea el directorio si no existe): resumen agregado de retrieval, tabla por pregunta (id, categoría, pregunta, hit, posición, scores top-4), hoja de revisión de generación (decisión 7: `respuesta_referencia`, respuesta obtenida, fuentes y columnas de valoración), detalle del fallback y apartado «Diagnóstico» con la estructura retrieval vs generación.
   - Códigos de salida: 0 correcto, 2 error de configuración/uso (mismo criterio que `scripts/prueba_fase1.py`).
7. **Escribir `tests/eval/test_evaluate.py`** (sin red): métricas con rankings sintéticos (acierto en posiciones 1/4/fuera, multi-página parcial, `sin_respuesta`), validación del dataset (casos inválidos) y comprobación de fallback con `InMemoryVectorStore` vacío + `FakeEmbedder` + `FakeLLM` (mensaje fijo, fuentes vacías, cero prompts). Importar las funciones puras con `sys.path` sobre `eval/`, sin importar `container` en el test.
8. **Verificación local en frío:** `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`. Todo debe pasar sin red ni credenciales.
9. **Ejecutar la evaluación** (requiere autorización del usuario por cuota de Gemini — embeddings + ~15–20 llamadas al LLM; si no se autoriza al agente, entregar instrucciones para que la ejecute el usuario):
   ```
   uv run --env-file .env python eval/evaluate.py
   ```
   Comprobar previamente el estado del corpus en BD: si `scripts/prueba_fase1.py ingesta ...` devuelve «duplicado», el PDF ya está ingestado y no hay que hacer nada; si no, ingerir los 3 PDFs con sus cursos.
10. **Primera pasada de valoración de generación** (decisión 7): rellenar las columnas de valoración de la hoja de revisión anclándose a `respuesta_referencia` y al contexto recuperado; entregar a revisión del usuario. En `sin_respuesta`, valorar explícitamente si el LLM se abstuvo.
11. **Completar el diagnóstico** en el `.md` generado (informe §20.3): clasificar cada fallo como de retrieval (página esperada ausente del top-4 o en mala posición) o de generación (respuesta incorrecta pese al contexto correcto, invención, abstención errónea, fuentes incorrectas), e incluir observaciones sobre scores de `sin_respuesta` como referencia para un futuro threshold.
12. **Sincronizar documentación:** registrar en `roadmap.md` la extensión del esquema del dataset (`id`, `documento`) y cualquier decisión derivada del diagnóstico; revisar `informe.md` §17 si el diagnóstico aporta datos que convenga fijar. Propagar según la regla «primero informe, después roadmap».
13. **Cerrar la fase:** archivar este plan en `docs/plans/2026-10-13-fase-2-evaluacion.md` y actualizar `MEMORY.md` (estado, baseline medido retrieval + generación, decisiones y próximos pasos). No dejar scripts temporales en el repo.

## Verificación

- `uv run pytest -q` — suite completa verde (incluidos `tests/adapters/ai/test_gemini_llm.py`, `tests/eval/` y `tests/test_container.py`), sin red.
- `uv run ruff check .` y `uv run ruff format --check .` — limpios.
- `uv run pytest -m integration -q` — no debe romperse (con configuración y autorización).
- Ejecución real: `uv run --env-file .env python eval/evaluate.py` genera `eval/resultados/<fecha>.md` con Hit@4 global y por categoría, la hoja de revisión de generación y la comprobación de fallback con mensaje fijo, fuentes vacías y cero llamadas al LLM.
- Inspección manual del `.md`: cada pregunta con hit=0 se puede razonar mirando scores y páginas; cada valoración de generación está justificada con `respuesta_referencia`.

## Criterios de aceptación

- Las 6 tareas de la Fase 2 del roadmap quedan cumplidas, incluida la evaluación de generación (tarea 5).
- Baseline documentado con `k = 4` y sin threshold en `eval/resultados/`.
- `eval/dataset.json` ejecutable, con ≥ 15 preguntas y distribución 7–8 / 5–6 / 4–5.
- La comprobación de retrieval vacío devuelve el mensaje fijo de `informe.md`, fuentes vacías y cero llamadas al LLM generativo (verificado con contador sobre el `GeminiLLM` real).
- El diagnóstico separa fallos de retrieval y de generación según el árbol del informe §20.3.
- `GeminiLLM` y su fábrica están probados; `GEMINI_LLM_MODEL_POR_DEFECTO` tiene consumidor.
- Suite local y Ruff en verde; sin residuos temporales en el repo.
- `MEMORY.md` y documentación sincronizada; plan archivado en `docs/plans/`.

## Riesgos

- **Referencias de página incorrectas** en el dataset (riesgo mayor): el Hit@k sería engañoso. Mitigación: cada `paginas_esperadas` se verifica contra el volcado de texto del paso 4 y se excluyen páginas omitidas por el filtro de 50 caracteres.
- **Páginas omitidas en la ingesta:** si la respuesta está en una página descartada, el retrieval nunca la devolverá; el diagnóstico debe anotarlo como limitación del chunking actual, no como fallo del retriever.
- **API del SDK `google-genai`:** la firma del método de generación debe verificarse contra la versión instalada; no copiar la API de memoria.
- **Valoración de generación subjetiva:** mitigación anclando cada valoración a `respuesta_referencia` y al contexto recuperado, con revisión final del usuario.
- **PDFs de Downloads ausentes o corpus modificado:** si un archivo no existe, avisar al usuario en lugar de sustituirlo; los 3 PDFs son el corpus aprobado.
- **Cuota de Gemini:** la ejecución consume ~1 embedding por pregunta, ~1 llamada LLM por pregunta con resultados y las llamadas del fallback (que no llegan a ocurrir). Requiere autorización explícita.

## Notas

- Regla del roadmap vigente: no cambiar `k`, el prompt ni el chunking sin comparar contra este baseline. El prompt de `Preguntar` (informe A.8) no se modifica en esta fase.
- El mensaje fijo solo se usa con retrieval de cero filas; con fragmentos aunque sean poco relevantes, el LLM responde según el contexto o indica falta de evidencia — la hoja de generación debe reflejarlo.
- No se crean comandos ni alias nuevos fuera de `eval/evaluate.py`; el CLI formal es la Fase 3.
- Los tests de `tests/eval/`, `tests/adapters/ai/` y el script temporal del paso 4 no deben dejar archivos temporales en el repo (regla del proyecto).
