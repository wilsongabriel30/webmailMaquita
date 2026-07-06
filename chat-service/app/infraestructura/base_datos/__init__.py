# -*- coding: utf-8 -*-
"""
Base de Datos - BRIDGE LEGACY

NOTA: Este modulo es un bridge de compatibilidad.
El codigo real esta en: compartido/infraestructura/base_datos/

Para nuevo codigo, usar:
    from compartido.infraestructura.base_datos import Base, obtener_gestor
"""

from infraestructura.base_datos.base import (
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
