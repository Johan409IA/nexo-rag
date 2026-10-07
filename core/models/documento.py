import re
from dataclasses import dataclass
from datetime import datetime

_HASH_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class Documento:
    """PDF completo ingestado en la base de conocimiento."""

    id: int | None
    nombre: str
    curso: str
    hash_sha256: str
    fecha_ingesta: datetime | None = None

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise ValueError("nombre no puede estar vacío")
        if not self.curso.strip():
            raise ValueError("curso no puede estar vacío")
        if not _HASH_SHA256.fullmatch(self.hash_sha256):
            raise ValueError("hash_sha256 debe ser 64 caracteres hexadecimales en minúsculas")
