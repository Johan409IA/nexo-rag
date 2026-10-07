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
