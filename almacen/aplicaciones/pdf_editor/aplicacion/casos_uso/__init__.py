# -*- coding: utf-8 -*-
"""
Casos de Uso - PDF Editor.

Cada caso de uso representa una acción específica del sistema.
"""

from .visualizar_documento import CasoUsoVisualizarDocumento
from .gestionar_paginas import CasoUsoGestionarPaginas

__all__ = [
    'CasoUsoVisualizarDocumento',
    'CasoUsoGestionarPaginas'
]
