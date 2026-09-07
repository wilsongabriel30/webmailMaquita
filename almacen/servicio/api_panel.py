# -*- coding: utf-8 -*-
"""API del Almacén para el panel de administración del correo (alta de buzones).

El panel corre en el mismo servidor y no comparte la configuración del Almacén (D-2). Habla
con este blueprint por loopback con un secreto propio (`ALMACEN_SECRETO_PANEL`, cabecera
`X-Almacen-Panel`), distinto del canal del chat. Sin secreto configurado, el canal no existe.

Lo que puede hacer el panel:
- ver el modo de directorio y la cuota por defecto;
- buscar personas del directorio central (modo «nómina») para VINCULAR un buzón a una persona
  que no tiene ese correo en el directorio (por ejemplo, alguien creado en Raíces con un
  correo personal): la tabla `enlaces_correo` manda sobre la coincidencia por correo;
- fijar la cuota del Drive de un buzón (0 = la de la organización).
"""
import hmac
import logging
import os

from flask import Blueprint, jsonify, request

from almacen_bd import consultar, ejecutar
from config_almacen import cuota_defecto_bytes

log = logging.getLogger('almacen.panel')
bp_panel = Blueprint('panel', __name__)

GB = 1024 ** 3
_LOOPBACK = ('127.0.0.1', '::1')


def _modo() -> str:
    return os.getenv('ALMACEN_MODO_DIRECTORIO', 'local').strip().lower()


@bp_panel.before_request
def _candado():
    secreto = os.getenv('ALMACEN_SECRETO_PANEL', '')
    cabecera = request.headers.get('X-Almacen-Panel', '')
    if not secreto or len(secreto) < 16:
        return jsonify({'success': False, 'error': 'Canal del panel no configurado'}), 503
    if request.remote_addr not in _LOOPBACK or not cabecera or not hmac.compare_digest(secreto, cabecera):
        log.warning('Canal del panel rechazado: ip=%s', request.remote_addr)
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    return None


@bp_panel.route('/config', methods=['GET'])
def config():
    return jsonify({'success': True, 'modo': _modo(), 'cuota_defecto_gb': round(cuota_defecto_bytes() / GB, 2)})


@bp_panel.route('/directorio', methods=['GET'])
def directorio():
    """Personas del directorio central (solo modo nómina), para vincular un buzón."""
    if _modo() != 'nomina':
        return jsonify({'success': True, 'modo': _modo(), 'personas': []})
    q = (request.args.get('q') or '').strip().lower()
    if len(q) < 2:
        return jsonify({'success': True, 'modo': 'nomina', 'personas': []})
    filas = consultar("""
        SELECT id, username, email, full_name
          FROM usuarios
         WHERE active = TRUE
           AND (LOWER(full_name) LIKE %s OR LOWER(email) LIKE %s OR LOWER(username) LIKE %s)
         ORDER BY full_name LIMIT 20
    """, (f'%{q}%', f'%{q}%', f'%{q}%'), nomina=True)
    return jsonify({'success': True, 'modo': 'nomina', 'personas': [dict(f) for f in filas]})


def _usuario_id(correo: str, crear: bool):
    """Id del usuario del Almacén para un buzón: enlace explícito, directorio central o local."""
    from auth_webmail import _buscar_en_nomina, _obtener_o_crear_local
    if _modo() == 'nomina':
        uid, _rol = _buscar_en_nomina(correo)
        return uid
    if crear:
        uid, _rol = _obtener_o_crear_local(correo)
        return uid
    filas = consultar('SELECT id FROM usuarios WHERE username = %s', (correo,))
    return filas[0]['id'] if filas else None


@bp_panel.route('/estado', methods=['GET'])
def estado():
    correo = (request.args.get('correo') or '').strip().lower()
    if '@' not in correo:
        return jsonify({'success': False, 'error': 'correo inválido'}), 400
    enlace = consultar('SELECT usuario_id FROM enlaces_correo WHERE correo = %s', (correo,))
    persona = None
    if enlace and _modo() == 'nomina':
        p = consultar('SELECT id, full_name, email, username FROM usuarios WHERE id = %s', (enlace[0]['usuario_id'],), nomina=True)
        persona = dict(p[0]) if p else None
    uid = _usuario_id(correo, crear=False)
    cuota = consultar('SELECT limite_bytes FROM cuotas WHERE usuario_id = %s', (uid,)) if uid else []
    uso = consultar('SELECT usado_bytes FROM cuotas_uso WHERE usuario_id = %s', (uid,)) if uid else []
    return jsonify({
        'success': True, 'modo': _modo(), 'usuario_id': uid, 'vinculado_a': persona,
        'cuota_gb': round(cuota[0]['limite_bytes'] / GB, 2) if cuota else 0,
        'cuota_efectiva_gb': round((cuota[0]['limite_bytes'] if cuota else cuota_defecto_bytes()) / GB, 2),
        'usado_gb': round(uso[0]['usado_bytes'] / GB, 2) if uso else 0,
    })


@bp_panel.route('/enlace', methods=['POST'])
def enlace():
    """Vincula (o desvincula con usuario_id nulo) un buzón a una persona del directorio central."""
    datos = request.get_json(silent=True) or {}
    correo = (datos.get('correo') or '').strip().lower()
    uid = datos.get('usuario_id')
    if '@' not in correo:
        return jsonify({'success': False, 'error': 'correo inválido'}), 400
    if _modo() != 'nomina':
        return jsonify({'success': False, 'error': 'Solo en modo directorio «nómina»'}), 400
    if uid in (None, '', 0):
        ejecutar('DELETE FROM enlaces_correo WHERE correo = %s', (correo,))
        log.info('panel: buzón %s desvinculado del directorio', correo)
        return jsonify({'success': True, 'vinculado': False})
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'usuario_id inválido'}), 400
    persona = consultar('SELECT id, full_name, email FROM usuarios WHERE id = %s AND active = TRUE', (uid,), nomina=True)
    if not persona:
        return jsonify({'success': False, 'error': 'La persona no existe o está inactiva en el directorio'}), 404
    ejecutar("""
        INSERT INTO enlaces_correo (correo, usuario_id) VALUES (%s, %s)
        ON CONFLICT (correo) DO UPDATE SET usuario_id = EXCLUDED.usuario_id, creado_en = NOW()
    """, (correo, uid))
    log.info('panel: buzón %s vinculado a la persona %s del directorio', correo, uid)
    return jsonify({'success': True, 'vinculado': True, 'persona': dict(persona[0])})


@bp_panel.route('/cuota', methods=['POST'])
def cuota():
    """Cuota del Drive de un buzón en GB; 0 = la de la organización. En modo local crea el usuario."""
    datos = request.get_json(silent=True) or {}
    correo = (datos.get('correo') or '').strip().lower()
    if '@' not in correo:
        return jsonify({'success': False, 'error': 'correo inválido'}), 400
    try:
        gb = float(datos.get('cuota_gb', 0) or 0)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'cuota_gb inválida'}), 400
    if gb < 0 or gb > 100000:
        return jsonify({'success': False, 'error': 'cuota_gb fuera de rango'}), 400
    uid = _usuario_id(correo, crear=True)
    if not uid:
        return jsonify({'success': False, 'error': 'El buzón no está en el directorio: vincúlalo primero a una persona'}), 404
    if gb > 0:
        ejecutar("""
            INSERT INTO cuotas (usuario_id, limite_bytes) VALUES (%s, %s)
            ON CONFLICT (usuario_id) DO UPDATE SET limite_bytes = EXCLUDED.limite_bytes
        """, (uid, int(gb * GB)))
    else:
        ejecutar('DELETE FROM cuotas WHERE usuario_id = %s', (uid,))
    log.info('panel: cuota del Drive de %s (usuario %s) = %s GB', correo, uid, gb or 'defecto')
    return jsonify({'success': True, 'usuario_id': uid, 'cuota_gb': gb, 'cuota_efectiva_gb': round((int(gb * GB) if gb > 0 else cuota_defecto_bytes()) / GB, 2)})
