# -*- coding: utf-8 -*-
"""
Base de Datos: Configuracion Base - BRIDGE LEGACY

NOTA: Este archivo es un bridge de compatibilidad.
El codigo real esta en: compartido/infraestructura/base_datos/base.py

Para nuevo codigo, usar:
    from compartido.infraestructura.base_datos import Base, obtener_gestor

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado: 2026-01-05
"""

# Re-exportar desde la nueva ubicacion
from compartido.infraestructura.base_datos.base import (
    Base,
    GestorBaseDatos,
    inicializar_base_datos,
    obtener_gestor,
    obtener_session,
)

__all__ = [
    'Base',
    'GestorBaseDatos',
    'inicializar_base_datos',
    'obtener_gestor',
    'obtener_session',
]
