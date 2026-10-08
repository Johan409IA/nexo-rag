from collections.abc import Iterator
from contextlib import contextmanager

from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg.errors import UniqueViolation

from adapters.database.connection import conectar
from core.models import Documento, Fragmento, ResultadoBusqueda
from core.use_cases.ingestar_documento import DocumentoDuplicadoError


class PgVectorStore:
    """``VectorStore`` sobre PostgreSQL con pgvector.

    Cada operación abre su propia conexión con ``conectar`` y registra el tipo
    ``vector``. El documento y sus fragmentos se guardan en una sola
    transacción; la colisión del ``hash_sha256`` se traduce a
    ``DocumentoDuplicadoError``. ``buscar`` usa la distancia coseno y devuelve
    ``score = 1 - distancia``.
    """

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    @contextmanager
    def _conexion(self) -> Iterator[Connection]:
        conexion = conectar(self._database_url)
        try:
            conexion.execute("SET search_path TO public, extensions")
            conexion.commit()
            register_vector(conexion)
            conexion.commit()
            yield conexion
        finally:
            conexion.close()

    def existe_hash(self, hash_sha256: str) -> bool:
        with self._conexion() as conexion:
            fila = conexion.execute(
                "SELECT 1 FROM public.documentos WHERE hash_sha256 = %s",
                (hash_sha256,),
            ).fetchone()
            return fila is not None

    def guardar_documento_con_fragmentos(
        self,
        documento: Documento,
        fragmentos: list[Fragmento],
        embeddings: list[list[float]],
    ) -> None:
        if len(fragmentos) != len(embeddings):
            raise ValueError("fragmentos y embeddings deben tener la misma longitud")

        with self._conexion() as conexion, conexion.transaction():
            documento_id = self._insertar_documento(conexion, documento)
            for fragmento, embedding in zip(fragmentos, embeddings, strict=True):
                conexion.execute(
                    "INSERT INTO public.fragmentos "
                    "(documento_id, texto, pagina, chunk_index, embedding) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        documento_id,
                        fragmento.texto,
                        fragmento.pagina,
                        fragmento.chunk_index,
                        Vector(embedding),
                    ),
                )

    def buscar(
        self,
        embedding: list[float],
        k: int = 4,
        curso: str | None = None,
    ) -> list[ResultadoBusqueda]:
        consulta = (
            "SELECT f.texto, d.nombre, d.curso, f.pagina, "
            "1 - (f.embedding OPERATOR(extensions.<=>) %s) AS score "
            "FROM public.fragmentos f "
            "JOIN public.documentos d ON d.id = f.documento_id "
        )
        parametros: list = [Vector(embedding)]
        if curso is not None:
            consulta += "WHERE d.curso = %s "
            parametros.append(curso)
        consulta += "ORDER BY f.embedding OPERATOR(extensions.<=>) %s LIMIT %s"
        parametros.extend([Vector(embedding), k])

        with self._conexion() as conexion:
            filas = conexion.execute(consulta, parametros).fetchall()

        return [
            ResultadoBusqueda(
                texto=texto,
                documento=nombre,
                curso=curso_documento,
                pagina=pagina,
                score=float(score),
            )
            for texto, nombre, curso_documento, pagina, score in filas
        ]

    @staticmethod
    def _insertar_documento(conexion: Connection, documento: Documento) -> int:
        try:
            fila = conexion.execute(
                "INSERT INTO public.documentos (nombre, curso, hash_sha256) "
                "VALUES (%s, %s, %s) RETURNING id",
                (documento.nombre, documento.curso, documento.hash_sha256),
            ).fetchone()
        except UniqueViolation as error:
            raise DocumentoDuplicadoError("El documento ya fue ingestado.") from error

        if fila is None or not isinstance(fila[0], int):
            raise RuntimeError("PostgreSQL no devolvió el id del documento insertado")

        return fila[0]
