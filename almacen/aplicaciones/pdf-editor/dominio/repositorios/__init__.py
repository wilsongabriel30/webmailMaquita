# -*- coding: utf-8 -*-
"""
Interfaces de Repositorios (Puertos) - PDF Editor.

Define los contratos que deben implementar los adaptadores
de persistencia en la capa de infraestructura.
"""

from .repositorio_documento import IRepositorioDocumento
from .repositorio_anotacion import IRepositorioAnotacion
from .repositorio_version import IRepositorioVersion

__all__ = [
    'IRepositorioDocumento',
    'IRepositorioAnotacion',
    'IRepositorioVersion'
]
