# -*- coding: utf-8 -*-
"""
Base de Datos Compartida - Sistema FARO

Gestión de conexiones y sesiones de base de datos.

USO:
    from compartido.infraestructura.base_datos import Base, obtener_gestor
    from compartido.infraestructura.base_datos import get_db_url, get_db_engine

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-05
"""

from compartido.infraestructura.base_datos.base import (
    Base,
    GestorBaseDatos,
    inicializar_base_datos,
    obtener_gestor,
    obtener_session,
)
from compartido.infraestructura.base_datos.configuracion import (
    get_db_config,
    get_db_url,
    get_db_engine,
    get_safe_db_url,
)

__all__ = [
    'Base',
    'GestorBaseDatos',
    'inicializar_base_datos',
    'obtener_gestor',
    'obtener_session',
    'get_db_config',
    'get_db_url',
    'get_db_engine',
    'get_safe_db_url',
]
