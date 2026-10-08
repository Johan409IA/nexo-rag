# Changelog

## Unreleased

### Added

- Núcleo de la Fase 0 (Arquitectura + puertos): modelos de dominio (`Documento`, `Fragmento`, `ResultadoBusqueda`, `Fuente`, `RespuestaRAG`), puertos como `Protocol` y casos de uso `BuscarFragmentos` y `Preguntar`.
- Fase 1 de ingesta + retrieval: SHA-256 por bloques, flujo de ingesta con descarte y reporte de páginas breves, `PyMuPDFLoader`, `PageChunker`, `GeminiEmbedder` por lotes con reintentos, `PgVectorStore` con persistencia transaccional y búsqueda coseno.
- Dependencias de adaptadores `pgvector`, `google-genai` y `pymupdf`; contrato reutilizable de `VectorStore`, tests unitarios de adaptadores y pruebas de integración Supabase.
- `container.py` como composition root sin efectos al importar, con fábricas explícitas para los adaptadores de Fase 1.
- `scripts/prueba_fase1.py` para revisar extracción, ingestar/reingestar, inspeccionar scores y validar el filtro por curso; no sustituye al CLI formal de Fase 3.
- Esquema pgvector de Supabase aplicado; ejecución de integración remota pendiente por conectividad del entorno.
