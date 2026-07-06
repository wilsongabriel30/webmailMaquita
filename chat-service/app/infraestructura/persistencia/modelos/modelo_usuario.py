# -*- coding: utf-8 -*-
"""
Modelo SQLAlchemy: Usuario - BRIDGE LEGACY

NOTA: Este archivo es un bridge de compatibilidad.
El codigo real esta en: modulos/usuarios/infraestructura/persistencia/modelos/modelo_usuario.py

Para nuevo codigo, usar:
    from modulos.usuarios.infraestructura.persistencia.modelos import ModeloUsuario

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado: 2026-01-05
"""

# Re-exportar desde la nueva ubicacion
from modulos.usuarios.infraestructura.persistencia.modelos.modelo_usuario import ModeloUsuario

__all__ = ['ModeloUsuario']
