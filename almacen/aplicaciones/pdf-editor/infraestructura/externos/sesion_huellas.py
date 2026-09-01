# -*- coding: utf-8 -*-
"""
Reconocer un documento que ya está en el servidor, para no subirlo otra vez.
===========================================================================
Al abrir el editor, el navegador deja el documento en el servidor. Eso está
bien la primera vez, pero se hacía SIEMPRE: al recargar la página, al abrir el
mismo archivo en otra pestaña, al volver al documento de ayer… y en una
proforma de 20 MB por una conexión de oficina eso es un minuto largo de subida
que no hacía ninguna falta, porque el mismo archivo ya estaba ahí.

Aquí se guarda, junto a cada documento, su huella (sha256 del contenido). Antes
de subir nada, el navegador pregunta «¿tienes ya este?» mandando solo la huella
—64 letras— y si el servidor lo tiene, se sigue trabajando con el que ya está.

Dos cuidados:

· La huella lleva pegado el sello del archivo (tamaño y fecha exacta). El
  documento cambia con cada edición —se guarda añadiendo al final—, así que una
  huella cuyo sello no cuadra con el archivo de ahora **no vale** y se descarta:
  jamás se le devuelve a nadie una sesión que ya no contiene lo que él tiene.
· Solo se busca entre los documentos de quien pregunta. Una huella no es una
  llave: aunque alguien acertara la de un documento ajeno, no encontraría nada.

Autoría: Equipo de Tecnología Maquita — 2026-08-18
"""

import logging
import os

logger = logging.getLogger(__name__)

SUFIJO = '.huella'


def _sello(ruta):
    """Tamaño y fecha exacta del archivo: si esto cambia, la huella caducó."""
    datos = os.stat(ruta)
    return '%d|%d' % (datos.st_size, datos.st_mtime_ns)


def anotar(carpeta, nombre, huella):
    """Deja anotada la huella del documento recién guardado."""
    if not huella:
        return
    ruta = os.path.join(carpeta, nombre + '.pdf')
    try:
        with open(os.path.join(carpeta, nombre + SUFIJO), 'w',
                  encoding='utf-8') as marca:
            marca.write('%s|%s' % (huella, _sello(ruta)))
    except OSError:
        # Sin anotación se sube otra vez, que es lo de siempre: no es un fallo.
        logger.debug('no se pudo anotar la huella de %s', nombre, exc_info=True)


def olvidar(carpeta, nombre):
    """La anotación se va con su documento."""
    try:
        os.unlink(os.path.join(carpeta, nombre + SUFIJO))
    except OSError:
        pass


def _anotada(carpeta, nombre):
    """La huella anotada, o None si no hay o si ya no cuadra con el archivo."""
    try:
        with open(os.path.join(carpeta, nombre + SUFIJO), encoding='utf-8') as marca:
            huella, tamano, fecha = marca.read().strip().split('|')
    except (OSError, ValueError):
        return None
    try:
        if _sello(os.path.join(carpeta, nombre + '.pdf')) != '%s|%s' % (tamano, fecha):
            return None                     # el documento cambió: ya no es ese
    except OSError:
        return None
    return huella


def buscar(carpeta, huella, tamano, es_mio):
    """El nombre del documento de esta persona que tiene esa huella, o None.

    `es_mio` decide, para un nombre dado, si el documento es de quien pregunta;
    lo pone quien llama, que es el que sabe de firmas y de usuarios.
    """
    if not huella or len(huella) != 64 or not huella.isalnum():
        return None
    try:
        nombres = os.listdir(carpeta)
    except OSError:
        return None
    for archivo in nombres:
        if not archivo.endswith(SUFIJO):
            continue
        nombre = archivo[:-len(SUFIJO)]
        try:
            if os.path.getsize(os.path.join(carpeta, nombre + '.pdf')) != tamano:
                continue                    # descarte barato antes de leer nada
        except OSError:
            continue
        if _anotada(carpeta, nombre) != huella:
            continue
        if not es_mio(nombre):
            continue
        return nombre
    return None
