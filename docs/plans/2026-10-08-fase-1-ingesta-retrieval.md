# Fase 1: Ingesta + retrieval — PDFs convertidos en conocimiento recuperable

## Objetivo

Implementar el flujo completo de ingesta (hash → carga PDF → chunking → embeddings → persistencia) y el retrieval por similitud con pgvector, de modo que los PDFs de `C:\Users\Johan Castillon\Downloads\Documentos` se conviertan en fragmentos recuperables con fuentes y scores, cumpliendo el «Hecho cuando» de la Fase 1 de `roadmap.md`.

## Contexto

- Fase 0 cerrada: `core/` tiene modelos y puertos; `BuscarFragmentos` y `Preguntar` ya implementados (`k=4`, sin threshold, mensaje fijo sin LLM con retrieval vacío). `IngestarDocumento.ejecutar` es esqueleto (`NotImplementedError("Fase 1")`).
- `informe.md` (fuente de verdad) trae código de referencia en el Anexo A: A.3 `calcular_sha256`, A.4 `PyMuPDFLoader`, A.5 `PageChunker`, A.6 `IngestarDocumento`, A.9 `GeminiEmbedder`.
- Carril Supabase preparado sin ejecutar: `adapters/database/schema.sql` (tablas `documentos`/`fragmentos`, `extensions.vector(768)`, UNIQUE en `hash_sha256`, RLS sin políticas para `anon`/`authenticated`), `adapters/database/connection.py` (`conectar(database_url)` con psycopg3), `tests/integration/test_supabase.py` (6 tests, marca `integration`, se omite sin `DATABASE_URL`).
- El contrato de `VectorStore` ya es una suite ejecutable en `tests/fakes/test_vector_store_contrato.py`.
- Dependencias nuevas pre-aprobadas (MEMORY/roadmap): `pgvector`, `google-genai`, `pymupdf`. `psycopg>=3.3.6` ya está en `pyproject.toml`.
- Autorización del usuario: ejecutar `schema.sql` contra Supabase, `uv run pytest -m integration` y llamadas reales a Gemini. Las pruebas manuales de ingesta/consultas las ejecuta el usuario con las instrucciones y el script que entregue el agente.
- Los 3 PDFs reales disponibles: `S07_s1 Escalabilidad y big data.pdf`, `S08_s1 Integración de sistemas de información.pdf`, `S09_s1 Seguridad, auditoría.pdf` (en `C:\Users\Johan Castillon\Downloads\Documentos`).

## Alcance

Incluye:

- `calcular_sha256` y el flujo completo de `IngestarDocumento`.
- `PyMuPDFLoader`, `PageChunker`, `GeminiEmbedder`, `PgVectorStore`.
- Cableado real en `container.py` (fábricas de adaptadores, sin efectos al importar).
- Contrato de `VectorStore` reutilizado para validar `PgVectorStore`.
- Script de pruebas manuales + instrucciones para el usuario.
- Ejecución del carril Supabase (esquema + tests de integración).

No incluye:

- CLI `nexo` (Fase 3), adaptador LLM Gemini (Fase 2), API, MCP ni frontend.
- Cambios en `k=4`, el prompt ni la estrategia de chunking (baseline de la Fase 2).
- OCR ni tipos de documento distintos de PDF.

## Decisiones

1. **`calcular_sha256`** se define como función de módulo en `core/use_cases/ingestar_documento.py` (A.3, lectura por bloques de 1 MiB, stdlib). Es el único consumidor y, al vivir en `core`, el caso de uso lo llama sin violar la regla de imports (`core/` solo stdlib + `core.*`, verificada por `tests/architecture/test_dependencias.py`).
2. **`PageChunker`** va en `adapters/chunking/page_chunker.py`: implementación del puerto `Chunker` sin dependencias externas; `core/` se mantiene en modelos, puertos y casos de uso (estructura de `AGENTS.md`).
3. **`GeminiEmbedder`** sigue A.9 con los prefijos textuales decididos en el informe (`title: none | text: ...` para documentos, `task: question answering | query: ...` para consultas). Se procesa por lotes de `TAMANO_LOTE = 50` textos y, ante errores de cuota (429 / `RESOURCE_EXHAUSTED`), hasta 3 reintentos con espera creciente (2 s, 4 s, 8 s). Se valida que cada vector devuelto tenga 768 dimensiones. Nota: el SDK ofrece `task_type` como alternativa; no se cambia sin comparar contra el baseline de la Fase 2.
4. **`PgVectorStore(database_url: str)`** en `adapters/database/pgvector_store.py`: abre una conexión por operación reutilizando `conectar()` de `adapters/database/connection.py`, registra el tipo con `pgvector.psycopg.register_vector` y pasa los vectores como `pgvector.Vector`. `guardar_documento_con_fragmentos` es una sola transacción (INSERT de documento + fragmentos; rollback total ante error) y traduce `UniqueViolation` → `DocumentoDuplicadoError`. `buscar` usa la distancia coseno `<=>` de pgvector y devuelve `score = 1 - distancia`, orden descendente, `k` y filtro opcional de `curso` por igualdad exacta (coherente con `InMemoryVectorStore`).
5. **Contrato reutilizable:** se extrae la suite de `tests/fakes/test_vector_store_contrato.py` a `tests/contratos/vector_store.py` (mixin con método fábrica `crear_store()`), y se ejecuta contra ambos implementaciones: `InMemoryVectorStore` (local) y `PgVectorStore` (marca `integration`).
6. **Las pruebas manuales las ejecuta el usuario**; el agente entrega `scripts/prueba_fase1.py` con subcomandos e instrucciones paso a paso. No se adelanta el CLI (Fase 3).
7. **Valor de `curso`** derivado del nombre del archivo: «Escalabilidad y big data», «Integración de sistemas de información», «Seguridad, auditoría».
8. **Secuencia de identidad del documento:** `nombre = Path(ruta).name`, hash sobre el contenido del archivo (el renombrar no altera identidad), `id=None` hasta persistir (A.6).
9. **Caso borde documentado:** un PDF cuyas páginas quedan todas omitidas se guarda igualmente con cero fragmentos y reporta todas sus páginas en `paginas_omitidas` (comportamiento de A.6, sin inventar reglas nuevas).

## Tareas

1. **Dependencias.** `uv add pgvector google-genai pymupdf` (justificadas en MEMORY/roadmap; `psycopg` ya está). No añadir nada más.

2. **Hash + ingesta completa** — `core/use_cases/ingestar_documento.py`:
   - Añadir `calcular_sha256(ruta: str) -> str` (A.3).
   - Implementar `IngestarDocumento.ejecutar(ruta, curso)` (A.6): hash → `store.existe_hash` → `DocumentoDuplicadoError`; `loader.leer(ruta)`; separar `paginas_omitidas` (texto con `strip()` < `MIN_CARACTERES_PAGINA = 50`) de las válidas (ya `strip()`eadas); `chunker.crear_fragmentos(...)`; `embedder.embed_documentos([f.texto ...])`; construir `Documento(id=None, nombre=Path(ruta).name, curso=curso, hash_sha256=...)`; `store.guardar_documento_con_fragmentos(...)`; devolver `ResultadoIngesta`.
   - Tests en `tests/core/use_cases/test_ingestar_documento.py`: eliminar `test_ejecutar_sigue_siendo_esqueleto` y cubrir con fakes (`tests/fakes/`): rechazo de duplicados, filtrado de páginas y `paginas_omitidas`, textos `strip()`eados, pipeline en orden (loader → chunker → embedder → store), `nombre` del archivo, caso de todas las páginas omitidas, `FileNotFoundError` con ruta inexistente.
   - Nuevo `tests/core/use_cases/test_calcular_sha256.py`: contenido conocido, archivo mayor que un bloque (1 MiB) y ruta inexistente.

3. **Chunker** — `adapters/chunking/page_chunker.py` (A.5): cada página → un `Fragmento(id=None, documento_id=None, ..., chunk_index=0)`, sin filtrado. Tests en `tests/adapters/chunking/test_page_chunker.py` (varias páginas, preservación de números de página, sin descartes).

4. **Lector PDF** — `adapters/pdf/pymupdf_loader.py` (A.4): `leer(ruta)` devuelve `(pagina, texto.strip())` desde 1, incluidas páginas vacías, `FileNotFoundError` si no existe. Tests en `tests/adapters/pdf/test_pymupdf_loader.py` generando un PDF mínimo con `pymupdf` en `tmp_path` (varias páginas, texto con espacios, página vacía, ruta inexistente).

5. **Embeddings Gemini** — `adapters/ai/gemini_embedder.py` (A.9): `GeminiEmbedder(api_key, dimensiones=768)`, modelo `gemini-embedding-2`, `output_dimensionality=768`, prefijos por tipo, lotes de 50, reintentos con espera ante cuota, `embed_documentos([]) == []`. Tests en `tests/adapters/ai/test_gemini_embedder.py` con el cliente `genai.Client` sustituido (monkeypatch): prefijos aplicados, tamaño de lote, reintentos, lista vacía y dimensión.

6. **Almacén pgvector** — `adapters/database/pgvector_store.py` (decisión 4): `existe_hash`, `guardar_documento_con_fragmentos` (transacción única; `ValueError` si `len(fragmentos) != len(embeddings)`; `UniqueViolation` → `DocumentoDuplicadoError` importado de `core.use_cases.ingestar_documento`), `buscar(embedding, k=4, curso=None)` con `SELECT ... ORDER BY f.embedding <=> %s LIMIT k` y `score = 1 - distancia`, JOIN a `documentos` para `nombre` y `curso`.

7. **Contrato reutilizable** — extraer la suite de `tests/fakes/test_vector_store_contrato.py` a `tests/contratos/vector_store.py`; `tests/fakes/test_vector_store_contrato.py` la usa con `InMemoryVectorStore`; nuevo `tests/integration/test_pgvector_store.py` (marca `integration`, `importorskip` de `psycopg`/`pgvector` y salto sin `DATABASE_URL`) la usa con `PgVectorStore`, con fixture que limpia las tablas antes de cada test.

8. **Cableado** — `container.py`: añadir fábricas de adaptadores sin efectos al importar, con parámetros explícitos (sin leer el entorno dentro de ellas): `construir_loader_pdf()`, `construir_chunker()`, `construir_embedder_gemini(gemini_api_key)`, `construir_vector_store(database_url)`. Mantener intactas las fábricas existentes. Tests en `tests/test_container.py` (tipos construidos y reload sin efectos).

9. **Script de pruebas manuales** — `scripts/prueba_fase1.py` (argparse, stdlib), que compone los puertos vía `container.py`:
   - `muestra <ruta_pdf>`: imprime por página los primeros ~200 caracteres del texto extraído (revisión de extracción).
   - `ingesta <ruta_pdf> --curso X`: ejecuta la ingesta, imprime resumen, nº de fragmentos y `paginas_omitidas`; si es duplicado, mensaje claro y código de salida 1.
   - `reingesta <ruta_pdf> --curso X`: reintenta el mismo archivo; debe terminar con código 1 y mensaje de duplicado.
   - `consultas`: ejecuta 5–10 consultas predefinidas sobre los 3 cursos e imprime pregunta, documento, página y score.
   - `filtro --curso X --consulta "..."`: búsqueda con filtro de curso.
   - Limpiar los recursos (conexiones) al terminar cada comando.

10. **Carril Supabase** (autorizado): verificar primero si el esquema existe (consulta a `information_schema`); si falta, aplicar `adapters/database/schema.sql` con un script temporal en el scratchpad vía `conectar()`. Después, `uv run pytest -m integration` (con `DATABASE_URL` disponible, p. ej. `uv run --env-file .env pytest -m integration`) y comprobar los 6 tests existentes + los nuevos del contrato de `PgVectorStore`.

11. **Verificación local completa** (ver sección siguiente).

12. **Documentación**: actualizar `MEMORY.md` (estado, decisiones con su porqué, errores a evitar; máx. ~50 líneas) y `CHANGELOG.md`; si surgiera una decisión que modifique el alcance o los contratos, propagarla primero a `informe.md` y después a `roadmap.md` (regla del proyecto). Prohibido guardar secretos.

## Verificación

Local (obligatoria):

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Esperado: todos los tests verdes (los de integración se omiten sin credenciales), Ruff limpio, y `tests/architecture/test_dependencias.py` sigue pasando (`core/` solo stdlib + `core.*`).

Pruebas manuales — a cargo del usuario, con estas instrucciones (PowerShell, desde `D:\Codigo\Proyectos\nexo`; `--env-file .env` carga `DATABASE_URL` y `GEMINI_API_KEY`, el agente nunca lee `.env`):

1. Revisión de extracción de los 3 PDFs:
   ```powershell
   uv run --env-file .env python scripts/prueba_fase1.py muestra "C:\Users\Johan Castillon\Downloads\Documentos\S07_s1 Escalabilidad y big data.pdf"
   ```
   Repetir con `S08_s1 Integración de sistemas de información.pdf` y `S09_s1 Seguridad, auditoría.pdf` y confirmar que el texto se lee correctamente.
2. Ingesta de un PDF:
   ```powershell
   uv run --env-file .env python scripts/prueba_fase1.py ingesta "C:\Users\Johan Castillon\Downloads\Documentos\S07_s1 Escalabilidad y big data.pdf" --curso "Escalabilidad y big data"
   ```
   Esperado: documento ingestado, nº de fragmentos y lista de páginas omitidas.
3. Reingestar el mismo archivo con el mismo comando `ingesta` (o `reingesta`): debe rechazarse con mensaje de duplicado y código de salida 1.
4. Consultas: `uv run --env-file .env python scripts/prueba_fase1.py consultas` → revisar 5–10 resultados inspeccionando scores y páginas.
5. Filtro de curso: `uv run --env-file .env python scripts/prueba_fase1.py filtro --curso "Seguridad, auditoría" --consulta "..."` → solo resultados de ese curso.

## Criterios de aceptación

- Una consulta devuelve la página correcta de un PDF conocido («Hecho cuando» de la Fase 1).
- El reingesto de un PDF ya ingerido se rechaza con `DocumentoDuplicadoError`.
- Las páginas omitidas se reportan en `ResultadoIngesta.paginas_omitidas`.
- La búsqueda respeta el filtro opcional de curso.
- `uv run pytest` y Ruff pasan; `core/` no importa SDKs; `container.py` sigue sin efectos al importar.
- `uv run pytest -m integration` en verde contra Supabase (esquema verificado/aplicado).

## Riesgos

- **Extracción imperfecta**: PDFs escaneados o diapositivas casi vacías quedan sin texto útil; el filtro de 50 caracteres los reporta como omitidos (sin OCR en el MVP).
- **Cuota de Gemini**: mitigada con lotes de 50 y reintentos con espera.
- **Carrera en duplicados**: protegida con el UNIQUE de `hash_sha256` → `UniqueViolation` → `DocumentoDuplicadoError` (la comprobación previa con `existe_hash` es solo conveniencia).
- **Orden de lectura**: `pymupdf` itera en orden del documento; la numeración de páginas se mantiene con `enumerate(..., start=1)`.

## Notas

- No tocar `k=4`, el prompt de `Preguntar` ni el chunking: son el baseline de la Fase 2.
- Mantener el contrato de `DocumentLoader` (incluye páginas vacías) y de `Embedder` (768 dimensiones, misma cardinalidad, `[] → []`).
- Los comandos del usuario usan `uv run --env-file .env ...`; no leer `.env` ni imprimir valores de secretos.
- `scripts/prueba_fase1.py` es herramienta de verificación manual reproducible (útil también como paso previo a la Fase 2); debe pasar Ruff.
