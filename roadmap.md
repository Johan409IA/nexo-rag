# Ruta de desarrollo: Nexo, asistente de estudio sobre PDFs

> **Versión:** MVP v1  
> **Inicio:** Fase 0  
> **Ritmo supuesto:** 8–10 h por semana  
> **Nota:** Las duraciones son estimaciones y pueden ajustarse.  
> **Fuente de verdad:** `informe.md` define el alcance y las decisiones; este roadmap las desglosa por fases. Si se aprueba una decisión nueva, actualizar primero el informe y después este roadmap y el plan de fase correspondiente.

## Resumen de fases

| Fase | Nombre                 | Duración est. | Resultado clave                                            |
| :--: | ---------------------- | :-----------: | ---------------------------------------------------------- |
|  0   | Arquitectura + puertos |   1 semana    | Núcleo probado localmente; Supabase se valida por separado |
|  1   | Ingesta + retrieval    |  1,5 semanas  | PDFs convertidos en fragmentos recuperables                |
|  2   | Evaluación             |   1 semana    | Baseline medido (`Hit@k`)                                  |
|  3   | CLI                    |  0,5 semanas  | `nexo ingest` y `nexo ask`                                 |
|  4   | MCP                    |  0,5 semanas  | `buscar_conocimiento` usable desde un agente               |
|  5   | API                    |  0,5 semanas  | `POST /ask` con CORS                                       |
|  6   | Frontend               |   1 semana    | Chat con fuentes                                           |
|  7   | Deploy                 |  0,5 semanas  | Vercel + Render + Supabase                                 |
|  8   | Mejoras RAG            |    Abierta    | Solo con datos de la evaluación                            |

**Total del MVP (fases 0–7):** unas **6–7 semanas**.

---

## Fase 0: Arquitectura + puertos

### Objetivo

Preparar y probar el núcleo en local, sin que las interfaces ni los servicios externos sean requisitos para cerrar la fase.

### Tareas

1. Preparar la estructura raíz `nexo/` con `core/`, `adapters/`, `api/`, `cli/`, `mcp_server/`, `eval/`, `frontend/`, `tests/`, `docs/plans/` y `container.py`.
2. Configurar el entorno raíz con `uv`, `pyproject.toml`, Ruff y `pytest`. En esta fase, mantener vacías las dependencias de runtime y usar solo herramientas de desarrollo; añadir cada dependencia cuando la consuma su fase. Versionar `.env.example` e ignorar `.env`; las credenciales externas no se requieren para probar el núcleo.
3. Implementar los modelos `Documento`, `Fragmento`, `ResultadoBusqueda`, `Fuente` y `RespuestaRAG` (Anexo A.1). `Fragmento` no contiene el vector como campo de dominio: el embedding se persiste en la base y se entrega en paralelo a `VectorStore`.
4. Definir los puertos como `Protocol`: `DocumentLoader`, `Chunker`, `Embedder`, `VectorStore` y `LLM` (A.2). En el MVP, `Embedder` produce vectores de 768 dimensiones para documentos y consultas.
5. Implementar `BuscarFragmentos` y `Preguntar` con fakes y pruebas. Los vectores sintéticos de `FakeEmbedder` también tienen 768 dimensiones. `Preguntar` devuelve el mensaje fijo sin llamar al LLM si el retrieval está vacío. Dejar `IngestarDocumento` como esqueleto en esta fase; el flujo de ingesta completo pertenece a la Fase 1.
6. Escribir `container.py` como _composition root_ para configuración e inyección: la configuración no exige credenciales externas y las fábricas reciben puertos ya construidos. No crear clientes ni conexiones, ni aparentar que los adaptadores productivos están listos; su cableado real pertenece a la Fase 1.

### Hecho cuando

**Cierre del núcleo:** `uv run pytest` pasa sin red, credenciales ni servicios externos; los tests verifican retrieval vacío y con resultados, dimensiones de embeddings, arquitectura hexagonal e importación de `container.py` sin efectos. Ruff también pasa y `core/` solo importa la biblioteca estándar y `core.*`.

**Estado de Supabase:** se registra por separado como pendiente o verificado; que esté pendiente no bloquea el cierre del núcleo. Debe estar listo antes de ejecutar las pruebas de integración de la Fase 1 que lo requieran.

> **Riesgo:** acoplar el `core` a un SDK.  
> **Regla:** nada en `core/` importa `google`, `pymupdf` ni `psycopg`.

### Carril independiente: preparación y verificación de Supabase

En paralelo o cuando haya credenciales y autorización, crear/verificar el esquema con pgvector en East US (Ohio), habilitar RLS sin políticas para `anon`/`authenticated`, revocar sus privilegios de tabla y comprobar `SELECT 1`, esquema y _roundtrip_. Estas operaciones externas no son criterio de cierre del núcleo.

---

## Fase 1: Ingesta + retrieval

### Objetivo

Lograr que los documentos se conviertan en conocimiento recuperable.

### Tareas

1. Implementar `calcular_sha256` leyendo el archivo por bloques (A.3).
2. Implementar `PyMuPDFLoader` (A.4) y revisar manualmente el texto extraído de **2–3 PDFs reales** antes de seguir.
3. Implementar `PageChunker`: cada página que recibe produce un fragmento con `chunk_index = 0`; no aplica filtros.
4. En `IngestarDocumento`, antes del chunker, omitir páginas cuyo texto extraído tras `strip()` tenga menos de 50 caracteres y devolver sus números en `ResultadoIngesta` para que el CLI advierta al usuario.
5. Implementar `GeminiEmbedder` con `gemini-embedding-2` a 768 dimensiones. Usar los prefijos distintos para documentos y consultas, y procesar los textos por lotes.
6. Implementar `PgVectorStore` con tres operaciones:
   - `existe_hash`
   - guardar el documento y sus fragmentos en una sola transacción
   - buscar por similitud con filtro opcional de curso
7. Completar `BuscarFragmentos` e `IngestarDocumento` (duplicado → `DocumentoDuplicadoError`).
8. Hacer pruebas manuales:
   - Ingestar un PDF.
   - Reingestarlo: debe rechazarse.
   - Lanzar 5–10 consultas inspeccionando los `score`.
   - Confirmar que la API/búsqueda respeta el filtro opcional de curso.

### Hecho cuando

Una consulta devuelve la página correcta de un PDF conocido, el duplicado se rechaza y las páginas omitidas se reportan desde el CLI.

> **Riesgos:** orden de lectura imperfecto, diapositivas casi vacías y límites de cuota de Gemini. Los lotes y los reintentos con espera ayudan con este último punto.

---

## Fase 2: Evaluación

### Objetivo

Fijar un baseline antes de construir más interfaces.

### Tareas

1. Ingestar un corpus representativo de **3 a 5 PDFs**.
2. Escribir `eval/dataset.json` con **15–20 o más preguntas**. Cada una lleva:
   - `pregunta`
   - `curso`
   - `categoria`
   - `paginas_esperadas`
   - una respuesta de referencia

   Distribución sugerida:
   - **Directas:** 7–8
   - **Multi-página:** 5–6
   - **Sin respuesta:** 4–5

3. Escribir `eval/evaluate.py` con el cálculo de `Hit@k`, la posición de la página correcta y los `score`.
4. Comprobar el caso de retrieval vacío: debe devolver el mensaje fijo definido en `informe.md`, fuentes vacías y cero llamadas al LLM generativo. La creación del embedding de consulta sí ocurre y consume cuota de embeddings.
5. Evaluar la generación de forma manual o semiautomática:
   - corrección
   - fidelidad al contexto
   - ausencia de invenciones
   - comportamiento ante preguntas sin respuesta
6. Guardar los resultados en `eval/resultados/AAAA-MM-DD.md` y escribir un diagnóstico separando fallos de _retrieval_ y de generación.

### Hecho cuando

Hay un baseline documentado con `k = 4` y sin _threshold_. El mensaje fijo se usa solo si el retrieval devuelve cero filas; si devuelve fragmentos aunque sean poco relevantes, se llama al LLM para que responda según el contexto o indique que falta evidencia.

> **Regla:** no cambiar `k`, el prompt ni el _chunking_ sin comparar contra este baseline.

---

## Fase 3: CLI

### Objetivo

Tener una interfaz completa de uso y administración.

### Tareas

1. Crear la app Typer en `cli/` con:
   ```bash
   nexo ingest <ruta> --curso "..."
   ```
2. Añadir:
   ```bash
   nexo ask "..." [--curso "..."]
   ```
3. Mostrar advertencias de páginas omitidas, código de salida `1` para duplicados y mensajes de error claros.
4. Imprimir las fuentes como `curso · documento · página`, deduplicadas en orden estable.
5. Registrar el _entry point_ `nexo` en el `pyproject.toml` único de la raíz.

### Hecho cuando

El flujo completo funciona desde la terminal sin lógica RAG dentro del CLI.

---

## Fase 4: MCP

### Objetivo

Permitir que los agentes consulten los apuntes.

### Tareas

1. Crear el servidor con FastMCP y la herramienta `buscar_conocimiento(consulta, k=4, curso=None)`.
2. Devolver `texto`, `documento`, `curso`, `pagina` y `score`. **No usar el LLM.**
3. Validar los parámetros: `k` debe estar entre 1 y 10.
4. Configurar un cliente (OpenCode o Claude Code) y probarlo con consultas reales.
5. Documentar la configuración del cliente en el `README`.

### Hecho cuando

Un agente recupera fragmentos y redacta su respuesta citando las páginas.

---

## Fase 5: API

### Objetivo

Exponer las consultas al frontend.

### Tareas

1. Crear la app FastAPI con `POST /ask`, con modelos Pydantic de entrada (`pregunta`, `curso` opcional) y de salida (`respuesta`, `fuentes`).
2. Añadir `GET /cursos` (para el selector) y `GET /health`.
3. Validar la entrada, incluida la longitud máxima de la pregunta, y manejar errores `4xx` y `5xx`.
4. Configurar CORS con orígenes configurables.
5. Evaluar un límite de tasa simple, porque no hay autenticación. `GET /cursos` puede requerir ampliar `VectorStore` con una operación de listado.
6. **No crear endpoint de ingesta.**

### Hecho cuando

`curl` o la documentación `/docs` devuelven respuestas estructuradas.

---

## Fase 6: Frontend

### Objetivo

Construir la experiencia visual de consulta.

### Tareas

1. Crear el proyecto con Vite + React y definir `VITE_API_URL`.
2. Construir el chat con:
   - campo de pregunta
   - selector opcional de curso
   - respuesta
   - sección de fuentes
3. Añadir los estados de carga y error.
4. Hacer el diseño adaptable a móvil.
5. Comprobar que no hay claves de Gemini ni cadenas de conexión a Supabase en el bundle; el frontend solo usa `VITE_API_URL` para comunicarse con FastAPI.

### Hecho cuando

Se puede preguntar y ver las fuentes contra la API local.

---

## Fase 7: Deploy

### Objetivo

Publicar el producto funcional.

### Tareas

1. Antes de nada, revisar los límites vigentes de Gemini, Supabase, Render y Vercel.
2. Desplegar FastAPI en Render con `DATABASE_URL`, `GEMINI_API_KEY` y `GEMINI_LLM_MODEL=gemini-2.5-flash`; el modelo no cambia durante el MVP.
3. Desplegar el frontend en Vercel con `VITE_API_URL`.
4. Ajustar el CORS definitivo al dominio de Vercel.
5. Ingestar los PDFs desde el CLI local contra la base de producción.
6. Hacer la prueba _end-to-end_ y una pasada por el checklist del MVP.

### Riesgo

El plan gratuito de Render puede “dormir” el servicio y la primera petición tardará. Hay que avisarlo en la interfaz.

---

## Fase 8: Mejoras RAG

Las mejoras se priorizan según los fallos detectados en la evaluación.

1. Ajustar `k` y evaluar un _threshold_.
2. _Chunking_ por tamaño con _overlap_.
3. Índice HNSW si crece el volumen.
4. _Reranking_ y búsqueda híbrida.
5. OCR para PDFs escaneados.
6. Nuevos tipos de documento.

> **Regla de evaluación:** cada mejora se mide contra el dataset de la Fase 2.

---

## Checklist final del MVP

- [ ] Ingesta desde el CLI
- [ ] Duplicados detectados por SHA-256
- [ ] Advertencias de páginas casi vacías
- [ ] Fragmentos y embeddings en Supabase, con RLS habilitado, sin políticas para `anon`/`authenticated` y con sus privilegios de tabla revocados
- [ ] Retrieval relevante con pgvector
- [ ] Dataset de evaluación ejecutable
- [ ] Respuesta con fuentes y mensaje fijo sin LLM generativo cuando el retrieval devuelve cero fragmentos
- [ ] CLI de consulta
- [ ] MCP con metadatos
- [ ] API FastAPI
- [ ] Frontend con fuentes
- [ ] Todo desplegado
- [ ] Evaluación documentada
