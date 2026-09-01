# -*- coding: utf-8 -*-
"""
Value Objects del dominio PDF Editor.
"""

from .tipos_pdf import (
    EstadoDocumento,
    TipoAnotacion,
    EstadoAnotacion,
    TipoCampoFormulario,
    TipoFirma,
    FormatoExportacion
)
from .coordenadas import BoundingBox, Posicion
from .permisos import PermisoDocumento, NivelAcceso

__all__ = [
    'EstadoDocumento',
    'TipoAnotacion',
    'EstadoAnotacion',
    'TipoCampoFormulario',
    'TipoFirma',
    'FormatoExportacion',
    'BoundingBox',
    'Posicion',
    'PermisoDocumento',
    'NivelAcceso'
]
