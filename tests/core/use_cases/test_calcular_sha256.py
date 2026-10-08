import hashlib

import pytest

from core.use_cases.ingestar_documento import calcular_sha256


def test_hash_de_contenido_conocido(tmp_path) -> None:
    ruta = tmp_path / "doc.pdf"
    ruta.write_bytes(b"hola mundo")

    assert calcular_sha256(str(ruta)) == hashlib.sha256(b"hola mundo").hexdigest()


def test_hash_lee_por_bloques_archivos_mayores_de_un_mib(tmp_path) -> None:
    contenido = b"x" * (1024 * 1024) + b"cola"
    ruta = tmp_path / "grande.pdf"
    ruta.write_bytes(contenido)

    assert calcular_sha256(str(ruta)) == hashlib.sha256(contenido).hexdigest()


def test_hash_de_ruta_inexistente_falla(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        calcular_sha256(str(tmp_path / "no-existe.pdf"))
