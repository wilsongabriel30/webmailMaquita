# -*- coding: utf-8 -*-
"""Dónde guarda su estado la consolidación ASC (producción y caja de arena).

Módulo mínimo, sin dependencias, para que lo pueda importar la API del Drive
sin cargar el consolidador entero (que configura el registro y abre libros).
"""
ESTADO_DIR = '/mnt/almacen/_sincronizacion-asc/estado-consolidados'
ESTADO_DIR_SANDBOX = '/mnt/almacen/_sincronizacion-asc/estado-consolidados-sandbox'
PREFIJO_SANDBOX = '/PRUEBAS FORMULARIOS/ASC/'


def estado_dir_de(ruta_virtual):
    """El directorio de estado que corresponde a un consolidado por su ruta."""
    return ESTADO_DIR_SANDBOX if (ruta_virtual or '').startswith(PREFIJO_SANDBOX) else ESTADO_DIR
