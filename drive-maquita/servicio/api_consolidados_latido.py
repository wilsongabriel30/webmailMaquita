# -*- coding: utf-8 -*-
"""Latido del editor sobre una matriz territorial (11/09/2026).

La gente no pulsa «guardar»: edita y cierra. Para que un cambio en una matriz
llegue al consolidado abierto de otra persona en segundos, la página del
editor manda un latido cada pocos segundos mientras la matriz está abierta:

    POST /api/almacen/consolidados/latido?ruta=<matriz>

Si la ruta es una matriz fuente (producción o caja de arena), se pide al
Document Server un guardado forzado. Si no hubo cambios desde el último,
contesta 4 y no cuesta nada; si los hubo, guarda y su callback (estado 6)
dispara el camino rápido de la consolidación. Si la ruta no es una matriz
fuente, se contesta `aplica: false` y la página deja de latir.
"""
import hashlib
import logging

from flask import Blueprint, jsonify, request

from api_archivos import error, usuario_actual
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual

log = logging.getLogger('almacen.consolidados.latido')

bp_consolidados_latido = Blueprint('consolidados_latido', __name__)


@bp_consolidados_latido.route('/consolidados/latido', methods=['POST'])
def latido():
    usuario = usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    try:
        from consolidados.enganche import es_matriz_fuente
        if not es_matriz_fuente(ruta):
            return jsonify({'success': True, 'aplica': False})
        from api_onlyoffice import _base_documento, _version_sesion
        from guardado_forzado import _pedir_forcesave, _sala_abierta
        doc_base = _base_documento(usuario, ruta)
        if not _sala_abierta(doc_base):
            return jsonify({'success': True, 'aplica': True, 'codigo': -1})
        doc_key = hashlib.sha1(f'{doc_base}:v{_version_sesion(doc_base)}'.encode()).hexdigest()[:20]
        codigo = _pedir_forcesave(doc_key)
        if codigo not in (0, 4):
            log.warning('latido %s: forcesave devolvió %s', ruta, codigo)
        return jsonify({'success': True, 'aplica': True, 'codigo': codigo})
    except Exception as excepcion:
        log.warning('latido %s: %s', ruta, excepcion)
        return jsonify({'success': False, 'aplica': True, 'error': str(excepcion)[:120]})
