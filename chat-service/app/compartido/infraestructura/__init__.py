# -*- coding: utf-8 -*-
"""
Infraestructura Compartida - Sistema FARO

Componentes de infraestructura compartidos entre modulos.

CONTENIDO:
- base_datos/: Configuracion y gestion de conexiones a BD
- configuracion/: Contenedor de dependencias

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-05
"""

from compartido.infraestructura.base_datos import (
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
