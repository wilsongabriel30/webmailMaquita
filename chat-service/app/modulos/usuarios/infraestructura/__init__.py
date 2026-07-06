# -*- coding: utf-8 -*-
"""
Infraestructura del Módulo Usuarios

CAPA: infraestructura
Exporta los adaptadores de infraestructura.
"""

from .persistencia import RepositorioUsuarioPostgreSQL, ModeloUsuario

__all__ = [
    'RepositorioUsuarioPostgreSQL',
    'ModeloUsuario',
]
