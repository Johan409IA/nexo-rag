# Fase 0: Arquitectura + puertos

> **Estado:** Completado el 2026-10-07 — núcleo implementado y verificado; carril Supabase pendiente de configuración y autorización · **Creado:** 2026-10-04 · **Actualizado:** 2026-10-07
> **Fuentes:** `informe.md` (fuente de verdad: §8–§9, §13–§14, §20.4, Anexos A.1–A.8) y `roadmap.md` (Fase 0).
> Plan de implementación: las tareas se ejecutan en orden y cada una tiene su verificación.

## Objetivo

Completar y probar el núcleo del RAG en local: modelos de dominio, puertos, casos de uso base, fakes en memoria, tests y `container.py`. El núcleo no depende de SDKs, red, credenciales ni servicios externos.

La preparación de Supabase (esquema, RLS y conexión) es un carril independiente: se ejecuta cuando haya configuración y autorización, se informa por separado y no bloquea el cierre de la fase.

## Contexto

- La estructura de carpetas ya existe (`core/`, `adapters/`, `api/`, `cli/`, `mcp_server/`, `eval/`, `frontend/`, `tests/`, `docs/plans/`); falta `container.py`.
- Entorno raíz con `uv`, Python 3.13.7, `pyproject.toml` sin dependencias de runtime (`pytest` y `ruff` en desarrollo), `.env.example` y `.gitignore` (incluye `*.pdf`) listos.
- Los módulos Python están vacíos: no hay casos de uso, adaptadores ni tests.
- Regla de dependencias: nada en `core/` importa `google`, `pymupdf` ni `psycopg`; se automatiza con un test de arquitectura.
- La documentación no debe presentar `nexo ...` ni `uv run fastapi dev` como utilizables: aún no existen el entry point ni la API.

## Alcance

| Incluye | No incluye (queda para su fase) |
| --- | --- |
| Modelos, puertos y casos de uso base | `calcular_sha256`, `PyMuPDFLoader`, `PageChunker` → Fase 1 |
| Fakes en memoria y tests del core | `GeminiEmbedder`, `GeminiLLM`, `PgVectorStore` → Fase 1 |
| `container.py`: configuración e inyección sin efectos | Dataset y `evaluate.py` → Fase 2 |
| `schema.sql`, conexión y test de integración de Supabase (carril independiente) | CLI `nexo` → Fase 3 · MCP → Fase 4 |
| Documentación mínima de cierre | `api/main.py` → Fase 5 · frontend → Fase 6 · deploy → Fase 7 · HNSW → Fase 8 |

## Decisiones de diseño

| ID | Decisión |
| --- | --- |
| D1 | Un único `pyproject.toml` en la raíz; `api/` es un paquete más. Ya aplicada. |
| D2 | `IngestarDocumento` filtra páginas con menos de 50 caracteres tras `strip()` y devuelve los números omitidos; `PageChunker` no filtra. |
| D3 | Modelos como `@dataclass(frozen=True, slots=True)` con validación mínima en `__post_init__` (refinamiento de implementación sobre A.1). |
| D4 | RLS habilitado en `documentos` y `fragmentos`, sin políticas para `anon`/`authenticated` y con sus privilegios de tabla revocados; sin `FORCE RLS`. |
| D5 | `DATABASE_URL` por session pooler (puerto 5432) (refinamiento operativo). |
| D6 | `container.py`: configuración e inyección explícita de puertos; sin clientes, conexiones ni efectos al importar. |
| D7 | Sin dependencias de runtime en Fase 0; cada dependencia se agrega en la fase que la consume. |
| D8 | `Preguntar` devuelve el mensaje fijo sin llamar al LLM solo cuando el retrieval devuelve cero filas; con resultados llama al LLM aunque el score sea bajo. El embedding de consulta siempre se genera. |
| D9 | Proyecto, distribución y ejecutable CLI: `nexo`. |
| D10 | La fase se cierra con pruebas locales del core; la validación de Supabase no bloquea. |
| D11 | `FakeEmbedder` produce vectores sintéticos de 768 dimensiones, igual que el contrato de `Embedder`. |

## Tareas de implementación

### 1. Modelos de dominio

Crear en `core/models/` (reexportados desde `core/models/__init__.py`; solo stdlib), según Anexo A.1:

| Archivo | Clase | Campos | Validación |
| --- | --- | --- | --- |
| `documento.py` | `Documento` | `id: int \| None`, `nombre`, `curso`, `hash_sha256`, `fecha_ingesta: datetime \| None = None` | `nombre` y `curso` no vacíos tras `strip`; `hash_sha256` de 64 hex en minúsculas |
| `fragmento.py` | `Fragmento` | `id`, `documento_id`, `texto`, `pagina`, `chunk_index` | `pagina >= 1`; `chunk_index >= 0` |
| `resultado_busqueda.py` | `ResultadoBusqueda` | `texto`, `documento`, `curso`, `pagina`, `score: float` | `pagina >= 1`; docstring: `score` es la similitud coseno (mayor = más similar) |
| `respuesta_rag.py` | `Fuente` | `documento`, `curso`, `pagina` | — |
| `respuesta_rag.py` | `RespuestaRAG` | `respuesta: str`, `fuentes: list[Fuente]` | — |

`Fragmento` no incluye el embedding: el vector se persiste en la base y viaja en una lista paralela a `VectorStore` (informe §8.2).

### 2. Puertos

Crear en `core/ports/` un archivo por puerto como `typing.Protocol`, con las firmas exactas del Anexo A.2 y el contrato documentado en cada docstring:

- `DocumentLoader.leer(ruta) -> list[tuple[int, str]]`: pares (página, texto) numerados desde 1, en orden y con texto ya `strip()`. Incluye páginas vacías (el filtrado es del caso de uso). `FileNotFoundError` si la ruta no existe.
- `Chunker.crear_fragmentos(paginas) -> list[Fragmento]`: recibe páginas ya filtradas; cada página produce un fragmento con `chunk_index = 0`.
- `Embedder.embed_documentos(textos) -> list[list[float]]` y `embed_consulta(consulta) -> list[float]`: misma cardinalidad y orden que la entrada, `[]` → `[]`, dimensión fija 768. El formato documento/consulta se aplica internamente (informe §11.1).
- `VectorStore`:
  - `existe_hash(hash_sha256) -> bool`;
  - `guardar_documento_con_fragmentos(documento, fragmentos, embeddings) -> None`: atómico; `ValueError` si `len(fragmentos) != len(embeddings)`; `DocumentoDuplicadoError` si el hash ya existe (protección frente a la carrera con `existe_hash`);
  - `buscar(embedding, k=4, curso=None) -> list[ResultadoBusqueda]`: orden descendente por `score`, como máximo `k`, `curso` por igualdad exacta.
- `LLM.responder(prompt: str) -> str`: texto plano.

### 3. Casos de uso

Crear en `core/use_cases/`; reciben los puertos por constructor y no importan SDKs:

- `buscar_fragmentos.py` — `BuscarFragmentos.ejecutar(consulta, k=K_POR_DEFECTO, curso=None)`: valida `consulta` no vacía y `k >= 1` (`ValueError`), genera el embedding con `embed_consulta` y delega en `VectorStore.buscar`. `K_POR_DEFECTO = 4` como constante única (no cambiar `k` sin baseline).
- `preguntar.py` — `Preguntar.ejecutar(pregunta, k=4, curso=None) -> RespuestaRAG`:
  - retrieval vacío → `MENSAJE_SIN_EVIDENCIA = "No encontré información suficiente en los apuntes disponibles para responder esta pregunta."` con `fuentes=[]`, sin llamar al LLM;
  - con resultados → contexto `[{curso}, {documento}, p. {pagina}]\n{texto}` y prompt que trata el contexto como datos (responder solo con el contexto, no inventar, indicar falta de evidencia, fidelidad a los fragmentos); fuentes deduplicadas en orden estable.
- `ingestar_documento.py` — esqueleto (A.6): `DocumentoDuplicadoError`, `ResultadoIngesta(documento, paginas_omitidas)`, `IngestarDocumento.MIN_CARACTERES_PAGINA = 50` y `ejecutar(ruta, curso)` que lanza `NotImplementedError("Fase 1")`. El flujo completo (hash, filtrado, chunking) es de la Fase 1.

### 4. Fakes en memoria

Crear en `tests/fakes/`:

- `FakeEmbedder`: vectores deterministas de 768 dimensiones (bolsa de palabras hasheada con `zlib.crc32`, nunca `hash()` de Python) y normalizados L2; registra las llamadas a `embed_documentos` y `embed_consulta`.
- `InMemoryVectorStore`: los tres métodos del puerto con similitud coseno, filtro exacto por `curso`, `ValueError` por longitudes distintas y `DocumentoDuplicadoError` por hash repetido.
- `FakeLLM`: respuesta fija y registro de los `prompts` recibidos.
- `FakeDocumentLoader`: devuelve las páginas con las que se construye.

### 5. Tests

Con `__init__.py` en `tests/` y sus subcarpetas (para poder importar `tests.fakes`):

- `tests/core/models/test_modelos.py`: construcción válida, inmutabilidad (`FrozenInstanceError`) y cada regla de validación.
- `tests/core/use_cases/test_buscar_fragmentos.py`: usa `embed_consulta` (nunca `embed_documentos`), respeta `k`, filtra por `curso`, ordena por `score`; `consulta` vacía o `k < 1` → `ValueError`.
- `tests/core/use_cases/test_preguntar.py`: el prompt contiene contexto y pregunta; fuentes deduplicadas y en orden estable; sin resultados → mensaje fijo y cero llamadas al LLM; el texto del LLM se devuelve intacto.
- `tests/core/use_cases/test_ingestar_documento.py`: construcción del esqueleto con fakes (el comportamiento se prueba en Fase 1).
- `tests/fakes/test_vector_store_contrato.py`: contrato de `VectorStore` sobre el fake — hash, atomicidad, dimensión 768, longitudes, `k`, filtro y orden. En Fase 1 se parametriza también con `PgVectorStore`.
- `tests/architecture/test_dependencias.py`: análisis AST — `core/` importa solo stdlib (`sys.stdlib_module_names`) y `core.*`; `adapters/` no importa `api`, `cli`, `mcp_server` ni `container`; `api/`, `cli/` y `mcp_server/` no importan `adapters` (solo `container` y `core`).

### 6. container.py y configuración

Crear `container.py` como composition root:

- `Configuracion`: dataclass inmutable con `database_url`, `gemini_api_key` y `gemini_llm_model` como valores de integración opcionales; los secretos nunca aparecen en `repr`.
- `cargar_configuracion()`: lee las variables de entorno del proceso con biblioteca estándar; no busca `.env` ni requiere `pydantic-settings`. `GEMINI_LLM_MODEL` conserva el valor fijo `gemini-2.5-flash`.
- Fábricas (p. ej. `construir_buscar_fragmentos(...)`, `construir_preguntar(...)`) que reciben puertos ya construidos y devuelven los casos de uso: no importan `adapters/`, no crean clientes ni abren conexiones. El cableado productivo de Gemini/PostgreSQL es de la Fase 1.
- Importar el módulo no lee configuración ni produce efectos; la lectura ocurre solo al invocar `cargar_configuracion()`.

Tests en `tests/test_container.py` (con `monkeypatch`, sin tocar `.env`): configuración sin variables de integración, parseo de entorno, `repr` sin secretos, fábricas conectando puertos fake a casos de uso, e importación del módulo sin efectos.

### 7. Preparación de Supabase (carril independiente)

Precondición: `DATABASE_URL` disponible y autorización explícita para cualquier operación contra el proyecto de Supabase (East US, Ohio). Sin ellos se dejan listos los artefactos y el test se omite con un mensaje claro. El resultado se informa por separado y no condiciona el cierre de la fase.

- `adapters/database/schema.sql` idempotente:

```sql
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

CREATE TABLE IF NOT EXISTS public.documentos (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre        TEXT        NOT NULL CHECK (btrim(nombre) <> ''),
    curso         TEXT        NOT NULL CHECK (btrim(curso) <> ''),
    hash_sha256   TEXT        NOT NULL UNIQUE CHECK (hash_sha256 ~ '^[0-9a-f]{64}$'),
    fecha_ingesta TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fragmentos (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    documento_id BIGINT NOT NULL REFERENCES public.documentos (id) ON DELETE CASCADE,
    texto        TEXT   NOT NULL,
    pagina       INT    NOT NULL CHECK (pagina >= 1),
    chunk_index  INT    NOT NULL CHECK (chunk_index >= 0),
    embedding    extensions.vector(768) NOT NULL,
    UNIQUE (documento_id, pagina, chunk_index)
);

ALTER TABLE public.documentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fragmentos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.documentos, public.fragmentos FROM anon, authenticated;
```

Sin índice vectorial (HNSW se evalúa en Fase 8) y sin índice sobre `curso`.

- `adapters/database/connection.py`: `conectar(database_url)` con `psycopg` y `connect_timeout=10`; único punto de conexión (lo reutilizará `PgVectorStore` en Fase 1).
- `tests/integration/test_supabase.py` con marcador `integration` (excluido por defecto): `SELECT 1`; extensión `vector` y su esquema; tablas, `UNIQUE`, `vector(768)`, RLS habilitado sin políticas ni privilegios de tabla para `anon`/`authenticated` y `relforcerowsecurity` falso; _roundtrip_ dentro de una transacción con `ROLLBACK` final (insertar documento y fragmento de 768 dimensiones, recuperar con `ORDER BY embedding <=> …`, duplicado → `UniqueViolation`, nada persistido tras el rollback).

### 8. Cierre de fase

- Ejecutar los comandos de verificación y dejar la suite local verde.
- Revisar `git status`: no deben prepararse `.env`, PDFs ni credenciales para commit.
- Documentación mínima (con aprobación): `AGENTS.md` (comandos, convenciones, reglas del dominio, verificación), `MEMORY.md` (estado y decisiones), `README.md` (requisitos, `uv sync`, `.env` solo para integraciones, cómo ejecutar los tests sin credenciales) y `CHANGELOG.md` con sección _Unreleased_.
- Actualizar la cabecera de este plan a **Completado** cuando se cumplan los criterios de aceptación.

## Archivos a crear o modificar

| Ruta | Acción | Contenido |
| --- | --- | --- |
| `core/models/*.py` | crear | Modelos A.1 con validaciones |
| `core/ports/*.py` | crear | Cinco `Protocol` con contrato documentado |
| `core/use_cases/*.py` | crear | `BuscarFragmentos`, `Preguntar`, esqueleto de `IngestarDocumento` |
| `container.py` | crear | Configuración e inyección sin efectos |
| `tests/fakes/`, `tests/core/`, `tests/architecture/`, `tests/test_container.py` | crear | Fakes y tests locales |
| `adapters/database/schema.sql`, `adapters/database/connection.py`, `tests/integration/test_supabase.py` | crear | Carril Supabase (ejecución externa solo con autorización) |
| `AGENTS.md`, `MEMORY.md`, `README.md`, `CHANGELOG.md` | actualizar | Documentación mínima de cierre |

## Verificación

```bash
uv run pytest                      # core + fakes + container: sin red, .env ni credenciales
uv run pytest tests/architecture   # reglas de dependencias
uv run pytest tests/test_container.py
uv run ruff check .
uv run ruff format --check .
```

Carril Supabase, por separado y solo con configuración y autorización:

```bash
uv run pytest -m integration
```

## Criterios de aceptación

- [ ] `uv run pytest` pasa sin red, `.env` ni credenciales (incluye retrieval vacío y con resultados).
- [ ] `core/` solo importa stdlib y `core.*` (test de arquitectura verde).
- [ ] `Embedder` documenta 768 dimensiones y `FakeEmbedder` produce vectores de 768.
- [ ] `Preguntar` devuelve el mensaje fijo sin llamar al LLM con retrieval vacío; con resultados llama al LLM aunque el score sea bajo.
- [ ] `container.py` se importa y se prueba sin efectos, sin clientes y sin secretos en `repr`.
- [ ] Ruff (`check` y `format --check`) limpio.
- [ ] Ningún secreto en archivos versionables.
- [ ] Supabase queda registrado como verificado o pendiente, sin bloquear el cierre.

## Riesgos

| Riesgo | Mitigación |
| --- | --- |
| Acoplar `core/` a un SDK | Test de arquitectura AST en cada ejecución de tests. |
| El tipo `vector` o el operador `<=>` no se resuelven (extensión en `extensions`) | El test de integración lo detecta; calificar el operador o fijar `search_path` en la conexión. |
| Fuga de secretos | Secretos invisibles en `repr`, `.env` ignorado, revisar `git status` en el cierre. |
| `gemini-embedding-2` con id o cuota distinta a la esperada | Verificar con un smoke check antes de la Fase 1 (no toca `core/`). |
| Proyecto Supabase Free pausado por inactividad | Reanudar desde el panel; solo demora el carril externo. |
| Sobre-diseño del núcleo | Alcance acotado: sin adaptadores reales ni interfaces en esta fase. |

## Notas para las fases siguientes

- **Fase 1 · embeddings:** cada texto debe ir en su propio `types.Content` (varios textos en una entrada producen un único embedding agregado); límite de 8.192 tokens por entrada. Añadir `psycopg`, `pgvector`, `google-genai` y `pymupdf` con sus adaptadores.
- **Fase 1 · `PgVectorStore`:** reutilizar `conectar()`, registrar `pgvector` con `psycopg` y traducir `UniqueViolation` a `DocumentoDuplicadoError`.
- **Fase 3:** registrar el ejecutable `nexo` en `[project.scripts]` y convertir el proyecto en paquete instalable (`[tool.uv] package = false` deja de aplicar).
- **Fase 5:** `GET /cursos` requiere una operación de listado en `VectorStore` que no existe en A.2.
- **Fase 7:** Render debe llegar a Supabase por IPv4 (probablemente session pooler); avisar del arranque en frío del plan gratuito.
- **Fase 8:** con filtro por `curso`, un índice HNSW/IVFFlat puede devolver menos de `k` filas; evaluar _iterative scan_ de pgvector.
