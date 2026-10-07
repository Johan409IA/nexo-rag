# Changelog

## Unreleased

### Added

- Núcleo de la Fase 0 (Arquitectura + puertos): modelos de dominio (`Documento`, `Fragmento`, `ResultadoBusqueda`, `Fuente`, `RespuestaRAG`), puertos como `Protocol` y casos de uso `BuscarFragmentos` y `Preguntar`, con `IngestarDocumento` como esqueleto para la Fase 1.
- `container.py` como composition root: configuración opcional desde variables de entorno, secretos invisibles en `repr` y fábricas de casos de uso por inyección de puertos, sin efectos al importar.
- Fakes en memoria (`FakeEmbedder` de 768 dimensiones, `InMemoryVectorStore`, `FakeLLM`, `FakeDocumentLoader`, `FakeChunker`) y suite de tests locales: modelos, casos de uso, contrato de `VectorStore`, reglas de arquitectura y configuración.
- Carril de Supabase preparado: `adapters/database/schema.sql` (pgvector, RLS sin políticas públicas y privilegios revocados), `adapters/database/connection.py` y test de integración omitido sin `psycopg`/`DATABASE_URL`.
