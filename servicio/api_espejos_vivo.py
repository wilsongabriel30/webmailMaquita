# -*- coding: utf-8 -*-
"""
Copias «siempre al día» abiertas en el editor: que se enteren de que cambiaron
=============================================================================
Una copia fiel se rehace en el DISCO cada vez que cambia su original. Pero si
alguien la tiene abierta, el editor sigue enseñando lo que cargó al abrirla: la
persona mira la copia, no ve el cambio y concluye que «no está conectada»
(28/09/2026).

La página del editor pregunta aquí cada pocos segundos:

    GET /api/almacen/espejos/vivo?ruta=<copia>[&primera=1]
        → {es_copia, marca}

`marca` cambia cada vez que la copia se rehace (`espejos_hoja` la anota en
Redis). Si cambia respecto a la que había al abrir, la página se recarga sola y
muestra la copia nueva. La primera pregunta (`primera=1`) mira en la base si el
archivo es una copia conectada; si no lo es, la página deja de preguntar. Las
siguientes solo leen Redis: no gastan conexiones de la base.

Montado sobre bp_vinculos (prefijo /api/almacen).

Autoría: Equipo de Tecnología Maquita — 2026-09-28
"""
import logging

from flask import jsonify, request

import api_vinculos as _v
import espejos_hoja
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual

log = logging.getLogger('almacen.api.espejos_vivo')


@_v.bp_vinculos.route('/espejos/vivo', methods=['GET'])
def espejo_vivo():
    usuario = _v.usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
    except RutaInvalida as excepcion:
        return _v.error(str(excepcion), excepcion.codigo)
    try:
        if request.args.get('primera'):
            from api_archivos import _permiso_unidad
            if not _permiso_unidad(usuario, ruta, escritura=False):
                return jsonify({'success': True, 'es_copia': False, 'marca': None})
            es_copia = bool(espejos_hoja._filas('destino', usuario, ruta))
            return jsonify({'success': True, 'es_copia': es_copia,
                            'marca': espejos_hoja.marca_de(usuario, ruta) if es_copia else None})
        return jsonify({'success': True, 'es_copia': True,
                        'marca': espejos_hoja.marca_de(usuario, ruta)})
    except Exception as excepcion:
        log.warning('espejo vivo %s: %s', ruta, excepcion)
        return jsonify({'success': False, 'es_copia': True, 'marca': None})
