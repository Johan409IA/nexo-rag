import pymupdf
import pytest

from adapters.pdf.pymupdf_loader import PyMuPDFLoader


def _crear_pdf(ruta, textos: list[str]) -> None:
    doc = pymupdf.open()
    for texto in textos:
        pagina = doc.new_page()
        if texto:
            pagina.insert_text((72, 72), texto)
    doc.save(str(ruta))
    doc.close()


def test_leer_numera_las_paginas_desde_uno(tmp_path) -> None:
    ruta = tmp_path / "doc.pdf"
    _crear_pdf(ruta, ["primera", "segunda", "tercera"])

    paginas = PyMuPDFLoader().leer(str(ruta))

    assert [numero for numero, _ in paginas] == [1, 2, 3]
    assert [texto for _, texto in paginas] == ["primera", "segunda", "tercera"]


def test_leer_incluye_paginas_vacias(tmp_path) -> None:
    ruta = tmp_path / "doc.pdf"
    _crear_pdf(ruta, ["texto", ""])

    paginas = PyMuPDFLoader().leer(str(ruta))

    assert paginas == [(1, "texto"), (2, "")]


def test_leer_devuelve_texto_strip(tmp_path) -> None:
    ruta = tmp_path / "doc.pdf"
    _crear_pdf(ruta, ["hola mundo"])

    paginas = PyMuPDFLoader().leer(str(ruta))

    assert all(texto == texto.strip() for _, texto in paginas)


def test_leer_ruta_inexistente_falla(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        PyMuPDFLoader().leer(str(tmp_path / "no-existe.pdf"))
