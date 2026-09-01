# -*- coding: utf-8 -*-
"""
El reconocimiento de tablas, recordado entre todos los procesos.
================================================================
Reconocer las tablas de una página cuesta ~0,34 s y el editor lo pide después de
cada edición. Ya se recordaba, pero **dentro de cada proceso**: con 3 workers de
gunicorn eran 3 memorias distintas de 24 fichas cada una, y al repartir ahora el
trabajo entre varios procesos (`pool_pdf`) esa memoria acertaría aún menos.

Aquí la memoria es **una sola para toda la máquina**: un archivo por ficha en
`/dev/shm` —que es memoria, no disco—, con el contenido del PDF y el número de
página como nombre. Cualquier worker y cualquier proceso del grupo encuentran lo
que otro calculó.

Lo que se guarda son medidas de rayas (números), no texto del documento; y se
borra solo al cabo de un rato (`VIDA`).

Autoría: Equipo de Tecnología Maquita — 2026-07-29
"""

import errno
import hashlib
import json
import logging
import os
import tempfile
import time

logger = logging.getLogger(__name__)

# Una carpeta por usuario del sistema: FARO corre como 'sistemas', pero las
# pruebas y el mantenimiento se hacen como root, y no deben dejar carpetas que
# el servicio luego no pueda escribir.
_CARPETA = os.path.join('/dev/shm' if os.path.isdir('/dev/shm')
                        else tempfile.gettempdir(),
                        'faro-pdf-tablas-%d' % os.getuid())

# Cuánto vive una ficha sin usarse. El editor vuelve sobre la misma página una y
# otra vez mientras se trabaja; media hora cubre de sobra una sesión de edición.
VIDA = 1800.0
# Techo de fichas guardadas, por si un día entran miles de documentos distintos.
MAXIMO = 4000
_ultimo_barrido = [0.0]


def _carpeta():
    try:
        os.makedirs(_CARPETA, mode=0o700, exist_ok=True)
    except OSError:
        pass
    return _CARPETA


def clave(contenido_pdf, numero_pagina):
    """La huella del documento y la página. El contenido entero: no se queda vieja."""
    return '%s-%d' % (hashlib.sha1(contenido_pdf).hexdigest(), int(numero_pagina))


def _ruta(clave_ficha):
    return os.path.join(_carpeta(), clave_ficha + '.json')


def obtener(clave_ficha):
    """Lo recordado, o None."""
    try:
        with open(_ruta(clave_ficha), 'rb') as archivo:
            return json.loads(archivo.read().decode('utf-8'))
    except (OSError, ValueError):
        return None


def guardar(clave_ficha, valor):
    """Recuerda el reconocimiento. Si no se puede, no pasa nada: se recalculará."""
    _barrer()
    ruta = _ruta(clave_ficha)
    try:
        # Se escribe al lado y se pone en su sitio de un tirón: otro proceso
        # leyendo a la vez ve la ficha entera o no la ve, nunca media.
        provisional = '%s.%d' % (ruta, os.getpid())
        with open(provisional, 'wb') as archivo:
            archivo.write(json.dumps(valor).encode('utf-8'))
        os.replace(provisional, ruta)
    except (OSError, ValueError) as excepcion:
        if getattr(excepcion, 'errno', None) == errno.ENOSPC:
            _vaciar()
        logger.debug('no se pudo recordar el reconocimiento: %s', excepcion)


def _barrer():
    """Fuera lo viejo y, si hay demasiadas fichas, fuera las menos recientes."""
    ahora = time.time()
    if ahora - _ultimo_barrido[0] < 60.0:
        return
    _ultimo_barrido[0] = ahora
    try:
        nombres = os.listdir(_carpeta())
    except OSError:
        return
    vivas = []
    for nombre in nombres:
        ruta = os.path.join(_CARPETA, nombre)
        try:
            edad = ahora - os.path.getmtime(ruta)
            if edad > VIDA:
                os.unlink(ruta)
            else:
                vivas.append((edad, ruta))
        except OSError:
            pass
    if len(vivas) > MAXIMO:
        vivas.sort(reverse=True)                      # las más viejas primero
        for _edad, ruta in vivas[:len(vivas) - MAXIMO]:
            try:
                os.unlink(ruta)
            except OSError:
                pass


def _vaciar():
    """Se acabó el sitio en /dev/shm: se empieza de cero antes que fallar."""
    try:
        for nombre in os.listdir(_CARPETA):
            try:
                os.unlink(os.path.join(_CARPETA, nombre))
            except OSError:
                pass
    except OSError:
        pass
