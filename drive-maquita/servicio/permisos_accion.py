# -*- coding: utf-8 -*-
"""¿Puede esta persona hacer esto AQUÍ?

Responsabilidad ÚNICA: responder sí o no sobre una ruta, para cualquier acción
que toque contenido. Es la misma pregunta que ya hacían subir, crear, copiar,
mover, renombrar y eliminar; aquí queda con un nombre público para que ninguna
acción nueva tenga que reinventarla —ni olvidarla, que es lo que pasaba con
guardar un diagrama, restaurar una versión o comentar.

El permiso se hereda por carpeta dentro de una unidad (modelo ampliativo, ver
`permisos_unidad_carpeta`): quien es editor de `/3 Guayas` escribe en Guayas y
en todo lo que cuelga de ella, y en ninguna otra.

FALLA CERRADO: cualquier error al comprobar es un «no».
"""

import logging

log = logging.getLogger('almacen.permisos_accion')


def _veredicto(usuario_id, ruta, escritura):
    from permisos_compartidos import permiso_compartido
    respuesta = permiso_compartido(usuario_id, ruta, escritura)
    if respuesta is not None:
        return respuesta
    from api_unidades import permiso_unidad
    return permiso_unidad(usuario_id, ruta, escritura)


def puede_leer(usuario_id, ruta) -> bool:
    """¿Puede ver lo que hay en esta ruta?"""
    try:
        return bool(_veredicto(usuario_id, ruta, False))
    except Exception as excepcion:
        log.warning('No se pudo comprobar la lectura de %s: %s', ruta, excepcion)
        return False


def puede_escribir(usuario_id, ruta) -> bool:
    """¿Puede cambiar lo que hay en esta ruta? Un lector nunca puede."""
    try:
        return bool(_veredicto(usuario_id, ruta, True))
    except Exception as excepcion:
        log.warning('No se pudo comprobar la escritura de %s: %s', ruta, excepcion)
        return False


def carpeta_de(ruta: str) -> str:
    """La carpeta donde vive esa ruta. El permiso de un archivo es el de su
    carpeta: no hay permisos por archivo suelto."""
    return (ruta or '').rsplit('/', 1)[0] or '/'


MOTIVO_LECTOR = ('No tienes permiso para hacer esto aquí. Pide edición de esta '
                 'carpeta a quien administra la unidad.')
