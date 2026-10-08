import os

import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("psycopg", reason="psycopg se instala con los adaptadores en la Fase 1")
pytest.importorskip("pgvector", reason="pgvector se instala con los adaptadores en la Fase 1")
conexion_mod = pytest.importorskip("adapters.database.connection")
store_mod = pytest.importorskip("adapters.database.pgvector_store")
contratos_mod = pytest.importorskip("tests.contratos.vector_store")

conectar = conexion_mod.conectar
PgVectorStore = store_mod.PgVectorStore
ContratoVectorStore = contratos_mod.ContratoVectorStore
HASH_UNO = contratos_mod.HASH_UNO
HASH_DOS = contratos_mod.HASH_DOS

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL is None:
    pytest.skip(
        "DATABASE_URL no configurada: el carril de Supabase queda pendiente",
        allow_module_level=True,
    )


@pytest.fixture(scope="session", autouse=True)
def limpiar_residuos_del_contrato():
    yield
    conexion = conectar(DATABASE_URL)
    try:
        conexion.execute(
            "DELETE FROM public.documentos WHERE hash_sha256 = ANY(%s)",
            ([HASH_UNO, HASH_DOS],),
        )
        conexion.commit()
    finally:
        conexion.close()


class TestPgVectorStore(ContratoVectorStore):
    @staticmethod
    def crear_store() -> PgVectorStore:
        conexion = conectar(DATABASE_URL)
        try:
            conexion.execute(
                "DELETE FROM public.documentos WHERE hash_sha256 = ANY(%s)",
                ([HASH_UNO, HASH_DOS],),
            )
            conexion.commit()
        finally:
            conexion.close()
        return PgVectorStore(DATABASE_URL)
