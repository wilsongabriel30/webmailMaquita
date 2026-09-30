# -*- coding: utf-8 -*-
"""
Formularios del Almacén — que el enlace de un `.forma` abra donde debe
=====================================================================
Dos tropiezos al abrir un formulario por su enlace (28/09/2026):

  · El enlace de «Compartir» lleva a `/archivos-almacen/editar`, que es el
    editor de documentos de Office: con un `.forma` respondía «Tipo de archivo
    no soportado: forma». Un formulario va a SU editor.
  · El enlace está armado en el espacio del DUEÑO. A quien se lo compartieron
    no le existe en el suyo: se le lleva por «Compartido conmigo»
    (`/compartido/<dueño>/…`), con el permiso que le dieron.

Autoría: Equipo de Tecnología Maquita — 2026-09-28
"""
import logging
from urllib.parse import quote

from seguridad_rutas import normalizar_ruta_virtual

log = logging.getLogger('almacen.formularios.enlace')

EDITOR = '/archivos-almacen/formulario'


def es_formulario(ruta):
    return str(ruta or '').lower().endswith('.forma')


def _por_compartido(usuario, ruta):
    """La misma ruta por «Compartido conmigo», o None si no hace falta."""
    try:
        from resolver_enlace import resolver
        destino = resolver(int(usuario), ruta) or {}
        return destino.get('ir_a')
    except Exception as excepcion:
        log.warning('enlace %s: no se pudo resolver (%s)', ruta, excepcion)
        return None


def desde_editor_de_documentos(usuario, ruta_bruta):
    """Si piden abrir un `.forma` en el editor de documentos, la dirección de
    su editor de formularios; None si no es un formulario."""
    try:
        ruta = normalizar_ruta_virtual(ruta_bruta or '')
    except Exception:
        return None
    if not es_formulario(ruta):
        return None
    return EDITOR + '?ruta=' + quote(_por_compartido(usuario, ruta) or ruta)


def desde_pagina(usuario, ruta_bruta, pagina):
    """Si la ruta pedida es del espacio de otra persona que se lo compartió,
    la misma página por «Compartido conmigo»; None si ya está bien."""
    try:
        ruta = normalizar_ruta_virtual(ruta_bruta or '')
    except Exception:
        return None
    if not es_formulario(ruta):
        return None
    compartida = _por_compartido(usuario, ruta)
    return (pagina + '?ruta=' + quote(compartida)) if compartida else None
