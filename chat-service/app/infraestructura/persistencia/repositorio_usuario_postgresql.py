# -*- coding: utf-8 -*-
"""
Adaptador: Repositorio Usuario PostgreSQL - BRIDGE LEGACY

NOTA: Este archivo es un bridge de compatibilidad.
El código real está en: modulos/usuarios/infraestructura/persistencia/repositorio_usuario_postgresql.py

Para nuevo código, usar:
    from modulos.usuarios import RepositorioUsuarioPostgreSQL

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado: 2026-01-04
"""

# Re-exportar desde la nueva ubicación
from modulos.usuarios.infraestructura.persistencia.repositorio_usuario_postgresql import (
    RepositorioUsuarioPostgreSQL,
)

__all__ = ['RepositorioUsuarioPostgreSQL']
