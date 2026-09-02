# -*- coding: utf-8 -*-
"""Endpoint de la tarjeta de enlaces: GET /api/almacen/enlace-info?url=…

Responsabilidad ÚNICA: exponer por HTTP lo que sabe `enlace_info`, con sesión
de FARO. Toda la lógica —y la comprobación de permisos— vive en ese módulo.
"""

import logging

from flask import Blueprint, jsonify, request

from enlace_info import contar, es_de_maquita

log = logging.getLogger('almacen.api_enlace_info')

bp_enlace_info = Blueprint('almacen_enlace_info', __name__)


def _usuario():
    """Quién pregunta. Sin sesión no se cuenta nada de nadie."""
    try:
        from flask_login import current_user
        if getattr(current_user, 'is_authenticated', False):
            return int(current_user.id)
    except Exception:
        pass
    cabecera = request.headers.get('X-Almacen-Usuario-Id')
    return int(cabecera) if cabecera else None


@bp_enlace_info.route('/enlace-info', methods=['GET'])
def enlace_info():
    url = (request.args.get('url') or '').strip()
    if not url:
        return jsonify({'success': False, 'error': 'Falta la dirección'}), 400

    usuario = _usuario()
    if not usuario:
        # Un invitado (editor de un enlace público) no tiene con qué comprobar
        # permisos: se le dice solo si la dirección es de este Drive.
        return jsonify({'success': True, 'es_maquita': es_de_maquita(url),
                        'acceso': False})

    try:
        datos = contar(usuario, url)
    except Exception as excepcion:
        # La tarjeta se dibuja igual, con lo que se deduce de la dirección: un
        # fallo aquí no puede dejar sin funcionar el clic en un enlace.
        log.warning('No se pudo describir el enlace: %s', excepcion)
        return jsonify({'success': True, 'es_maquita': es_de_maquita(url),
                        'acceso': False})

    datos['success'] = True
    return jsonify(datos)


@bp_enlace_info.route('/personas-del-archivo', methods=['GET'])
def personas_del_archivo():
    """GET /personas-del-archivo?ruta=…&q=…

    Quién puede entrar en ese archivo —para repartir permisos sobre los
    intervalos protegidos— y, si se escribe algo en `q`, a quién más se podría
    añadir de la nómina.
    """
    usuario = _usuario()
    if not usuario:
        return jsonify({'success': False, 'personas': [], 'nomina': []}), 200
    ruta = (request.args.get('ruta') or '').strip()
    busqueda = (request.args.get('q') or '').strip()
    try:
        from personas_archivo import con_acceso, buscar_en_nomina
        personas = con_acceso(usuario, ruta) if ruta else []
        yaEstan = set(p['id'] for p in personas)
        nomina = [p for p in buscar_en_nomina(busqueda) if p['id'] not in yaEstan] \
            if busqueda else []
    except Exception as excepcion:
        log.warning('No se pudieron listar las personas de %s: %s', ruta, excepcion)
        personas, nomina = [], []
    return jsonify({'success': True, 'personas': personas, 'nomina': nomina})
