# -*- coding: utf-8 -*-
"""Versiones y autoguardado del editor — Drive Maquita (26/11/2026).

PROBLEMA QUE RESUELVE
El Document Server guarda en el Drive cada 10 minutos mientras el documento
sigue abierto (autoAssembly: callback status 6 con forcesavetype 2). Así, si
falla el servidor de documentos, lo máximo expuesto son esos minutos.

Cada guardado pasa por `nucleo.subir`, que conserva el contenido anterior como
versión. Con un guardado cada 10 minutos, un libro editado todo el día llenaría
el tope de 100 versiones y se perdería el historial antiguo.

REGLA
Un autoguardado por temporizador solo crea versión si la última versión del
archivo tiene 30 minutos o más. Los guardados al cerrar (status 2), el botón
«Guardar» y los guardados pedidos por el Drive (descargas) versionan siempre.

Ante cualquier duda (error de BD, archivo sin versiones) se versiona: es
preferible una versión de más a una de menos.
"""

import logging

from almacen_bd import consultar

log = logging.getLogger('almacen.onlyoffice.versiones')

MINUTOS_ENTRE_VERSIONES = 30
AUTOGUARDADO_TEMPORIZADOR = 2   # forcesavetype del Document Server


def es_autoguardado(cuerpo: dict) -> bool:
    """True si el callback es un guardado por temporizador (autoAssembly)."""
    try:
        return (cuerpo.get('status') == 6
                and int(cuerpo.get('forcesavetype', -1)) == AUTOGUARDADO_TEMPORIZADOR)
    except (TypeError, ValueError):
        return False


def debe_versionar(usuario_id: int, ruta_virtual: str) -> bool:
    """¿Conviene guardar el contenido actual como versión antes de un autoguardado?"""
    try:
        import nucleo_archivos as nucleo
        file_id = nucleo._id_estable(usuario_id, ruta_virtual)
        filas = consultar("""
            SELECT (NOW() - MAX(creado_en)) < make_interval(mins => %s) AS reciente
            FROM versiones WHERE usuario_id = %s AND file_id = %s
        """, (MINUTOS_ENTRE_VERSIONES, usuario_id, file_id))
        reciente = bool(filas and filas[0].get('reciente'))
        return not reciente
    except Exception as excepcion:
        log.warning('debe_versionar %s: %s; se versiona', ruta_virtual, excepcion)
        return True
