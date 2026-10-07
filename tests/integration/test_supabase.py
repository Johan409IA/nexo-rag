import os

import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("psycopg", reason="psycopg se instala con los adaptadores en la Fase 1")
errors = pytest.importorskip("psycopg.errors")
conexion_mod = pytest.importorskip("adapters.database.connection")
conectar = conexion_mod.conectar

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL is None:
    pytest.skip(
        "DATABASE_URL no configurada: el carril de Supabase queda pendiente",
        allow_module_level=True,
    )


@pytest.fixture
def conexion():
    conn = conectar(DATABASE_URL)
    yield conn
    conn.rollback()
    conn.close()


def test_select_1(conexion) -> None:
    assert conexion.execute("SELECT 1").fetchone()[0] == 1


def test_extension_vector_en_esquema_extensions(conexion) -> None:
    fila = conexion.execute(
        "SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace "
        "WHERE e.extname = 'vector'"
    ).fetchone()

    assert fila is not None
    assert fila[0] == "extensions"


def test_esquema_y_restricciones(conexion) -> None:
    tablas = conexion.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name IN ('documentos', 'fragmentos')"
    ).fetchone()[0]
    assert tablas == 2

    hash_unico = conexion.execute(
        "SELECT count(*) FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
        "WHERE tc.table_schema = 'public' AND tc.table_name = 'documentos' "
        "  AND tc.constraint_type = 'UNIQUE' AND kcu.column_name = 'hash_sha256'"
    ).fetchone()[0]
    assert hash_unico == 1

    dimension = conexion.execute(
        "SELECT a.atttypmod FROM pg_attribute a "
        "JOIN pg_class c ON c.oid = a.attrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname = 'fragmentos' AND a.attname = 'embedding'"
    ).fetchone()[0]
    assert dimension == 768


def test_rls_habilitado_sin_politicas_publicas(conexion) -> None:
    for tabla in ("public.documentos", "public.fragmentos"):
        fila = conexion.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = %s::regclass",
            (tabla,),
        ).fetchone()
        assert fila[0] is True, f"{tabla} sin RLS habilitado"
        assert fila[1] is False, f"{tabla} con FORCE RLS"

    politicas = conexion.execute(
        "SELECT count(*) FROM pg_policies "
        "WHERE schemaname = 'public' AND tablename IN ('documentos', 'fragmentos') "
        "  AND roles && ARRAY['anon', 'authenticated']::name[]"
    ).fetchone()[0]
    assert politicas == 0


def test_privilegios_de_tabla_revocados(conexion) -> None:
    for rol in ("anon", "authenticated"):
        for tabla in ("public.documentos", "public.fragmentos"):
            for privilegio in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                otorgado = conexion.execute(
                    "SELECT has_table_privilege(%s, %s, %s)", (rol, tabla, privilegio)
                ).fetchone()[0]
                assert otorgado is False, f"{rol} conserva {privilegio} sobre {tabla}"


def test_roundtrip_con_rollback(conexion) -> None:
    hash_sha256 = "f" * 64
    vector = "[" + ",".join(["0.25"] * 768) + "]"

    conexion.execute(
        "INSERT INTO public.documentos (nombre, curso, hash_sha256) VALUES (%s, %s, %s)",
        ("roundtrip.pdf", "Curso de prueba", hash_sha256),
    )
    conexion.execute(
        "INSERT INTO public.fragmentos (documento_id, texto, pagina, chunk_index, embedding) "
        "SELECT id, %s, 1, 0, %s::extensions.vector FROM public.documentos WHERE hash_sha256 = %s",
        ("texto de prueba", vector, hash_sha256),
    )

    with pytest.raises(errors.UniqueViolation):
        with conexion.transaction():
            conexion.execute(
                "INSERT INTO public.documentos (nombre, curso, hash_sha256) VALUES (%s, %s, %s)",
                ("duplicado.pdf", "Curso de prueba", hash_sha256),
            )

    distancia = conexion.execute(
        "SELECT f.embedding OPERATOR(extensions.<=>) %s::extensions.vector "
        "FROM public.fragmentos f JOIN public.documentos d ON d.id = f.documento_id "
        "WHERE d.hash_sha256 = %s",
        (vector, hash_sha256),
    ).fetchone()[0]
    assert float(distancia) < 1e-6

    conexion.rollback()

    restantes = conexion.execute(
        "SELECT count(*) FROM public.documentos WHERE hash_sha256 = %s", (hash_sha256,)
    ).fetchone()[0]
    assert restantes == 0
