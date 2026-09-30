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

28/09/2026: vale también para cualquier libro del que beban copias «siempre al
día» (`espejos_hoja`) o vínculos de datos: el guardado forzado dispara
`refrescar_por_origen` y las copias se actualizan mientras se edita el original.
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
        segundos = 8
        if not es_matriz_fuente(ruta):
            # También los libros de los que beben copias «siempre al día» o
            # vínculos de datos (28/09/2026): sin el guardado forzado, lo que se
            # escribe en el original no llega a sus copias hasta que se cierra.
            if not _alimenta_copias(ruta):
                return jsonify({'success': True, 'aplica': False})
            segundos = 10
        from api_onlyoffice import _base_documento, _version_sesion
        from guardado_forzado import _pedir_forcesave, _sala_abierta
        doc_base = _base_documento(usuario, ruta)
        if not _sala_abierta(doc_base):
            return jsonify({'success': True, 'aplica': True, 'codigo': -1,
                            'segundos': segundos})
        doc_key = hashlib.sha1(f'{doc_base}:v{_version_sesion(doc_base)}'.encode()).hexdigest()[:20]
        codigo = _pedir_forcesave(doc_key)
        if codigo not in (0, 4):
            log.warning('latido %s: forcesave devolvió %s', ruta, codigo)
        return jsonify({'success': True, 'aplica': True, 'codigo': codigo,
                        'segundos': segundos})
    except Exception as excepcion:
        log.warning('latido %s: %s', ruta, excepcion)
        return jsonify({'success': False, 'aplica': True, 'error': str(excepcion)[:120]})


# Si un libro alimenta copias se pregunta a la base como mucho cada 30 s por
# proceso: el latido llega cada pocos segundos por cada libro abierto.
_memoria = {}
SEGUNDOS_MEMORIA = 30


def _alimenta_copias(ruta):
    import time
    ahora = time.time()
    dato = _memoria.get(ruta)
    if dato and dato[0] > ahora:
        return dato[1]
    import almacen_bd as bd
    alimenta = False
    for tabla in ('espejos_hoja', 'vinculos_datos'):
        try:
            if bd.consultar('SELECT 1 FROM %s WHERE activo AND origen_ruta = %%s '
                            'AND origen_ruta <> destino_ruta LIMIT 1' % tabla, (ruta,)):
                alimenta = True
                break
        except Exception as excepcion:          # la tabla aún no existe
            log.info('latido %s: %s', tabla, excepcion)
    if len(_memoria) > 500:
        _memoria.clear()
    _memoria[ruta] = (ahora + SEGUNDOS_MEMORIA, alimenta)
    return alimenta
