import hashlib
from dataclasses import dataclass
from pathlib import Path

from core.models import Documento
from core.ports.chunker import Chunker
from core.ports.document_loader import DocumentLoader
from core.ports.embedder import Embedder
from core.ports.vector_store import VectorStore


class DocumentoDuplicadoError(Exception):
    """El hash del documento ya existe en el almacén."""


@dataclass(frozen=True, slots=True)
class ResultadoIngesta:
    """Documento ingestado junto con los números de página omitidos."""

    documento: Documento
    paginas_omitidas: list[int]


def calcular_sha256(ruta: str) -> str:
    """Devuelve el hash SHA-256 del contenido del archivo, leído por bloques de 1 MiB."""
    hasher = hashlib.sha256()

    with Path(ruta).open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            hasher.update(bloque)

    return hasher.hexdigest()


class IngestarDocumento:
    """Convierte un PDF en fragmentos vectorizados.

    Omite las páginas cuyo texto extraído, tras ``strip()``, tiene menos de
    ``MIN_CARACTERES_PAGINA`` caracteres y devuelve sus números en
    ``ResultadoIngesta``. ``PageChunker`` no aplica este filtro. Un documento
    cuyas páginas se omiten todas se guarda igualmente, sin fragmentos.
    """

    MIN_CARACTERES_PAGINA = 50

    def __init__(
        self,
        loader: DocumentLoader,
        chunker: Chunker,
        embedder: Embedder,
        store: VectorStore,
    ) -> None:
        self.loader = loader
        self.chunker = chunker
        self.embedder = embedder
        self.store = store

    def ejecutar(self, ruta: str, curso: str) -> ResultadoIngesta:
        hash_sha256 = calcular_sha256(ruta)
        if self.store.existe_hash(hash_sha256):
            raise DocumentoDuplicadoError("El PDF ya fue ingestado.")

        paginas = self.loader.leer(ruta)
        paginas_omitidas = [
            pagina for pagina, texto in paginas if len(texto.strip()) < self.MIN_CARACTERES_PAGINA
        ]
        paginas_validas = [
            (pagina, texto.strip())
            for pagina, texto in paginas
            if len(texto.strip()) >= self.MIN_CARACTERES_PAGINA
        ]

        fragmentos = self.chunker.crear_fragmentos(paginas_validas)
        embeddings = self.embedder.embed_documentos([fragmento.texto for fragmento in fragmentos])
        documento = Documento(
            id=None,
            nombre=Path(ruta).name,
            curso=curso,
            hash_sha256=hash_sha256,
        )
        self.store.guardar_documento_con_fragmentos(documento, fragmentos, embeddings)
        return ResultadoIngesta(documento=documento, paginas_omitidas=paginas_omitidas)
