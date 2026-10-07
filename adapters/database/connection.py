import psycopg


def conectar(database_url: str) -> psycopg.Connection:
    """Abre la conexión PostgreSQL directa que usan backend y CLI.

    ``connect_timeout`` evita esperas indefinidas y el SSL se configura en la
    propia URL (``?sslmode=require``). Es el único punto de conexión del
    proyecto: ``PgVectorStore`` lo reutilizará en la Fase 1.
    """
    return psycopg.connect(database_url, connect_timeout=10)
