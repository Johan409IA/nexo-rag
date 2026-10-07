"""Modelos de dominio del asistente de estudio."""

from core.models.documento import Documento
from core.models.fragmento import Fragmento
from core.models.respuesta_rag import Fuente, RespuestaRAG
from core.models.resultado_busqueda import ResultadoBusqueda

__all__ = [
    "Documento",
    "Fragmento",
    "Fuente",
    "RespuestaRAG",
    "ResultadoBusqueda",
]
