import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PAQUETES_INTERFAZ = ("api", "cli", "mcp_server")


def _modulos_importados(archivo: Path) -> set[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                modulos.add(alias.name.split(".")[0])
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            modulos.add(nodo.module.split(".")[0])
    return modulos


def _archivos_python(paquete: str) -> list[Path]:
    return sorted((RAIZ / paquete).rglob("*.py"))


def test_core_solo_importa_stdlib_y_core() -> None:
    permitidos = set(sys.stdlib_module_names) | {"core"}

    for archivo in _archivos_python("core"):
        prohibidos = _modulos_importados(archivo) - permitidos
        assert not prohibidos, f"{archivo.relative_to(RAIZ)} importa {sorted(prohibidos)}"


def test_adapters_no_importa_interfaces_ni_container() -> None:
    prohibidos = set(PAQUETES_INTERFAZ) | {"container"}

    for archivo in _archivos_python("adapters"):
        encontrados = _modulos_importados(archivo) & prohibidos
        assert not encontrados, f"{archivo.relative_to(RAIZ)} importa {sorted(encontrados)}"


def test_interfaces_no_importan_adapters() -> None:
    for paquete in PAQUETES_INTERFAZ:
        for archivo in _archivos_python(paquete):
            assert "adapters" not in _modulos_importados(archivo), (
                f"{archivo.relative_to(RAIZ)} importa adapters"
            )
