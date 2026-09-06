# -*- coding: utf-8 -*-
"""
Grabaciones vistas desde Reuniones (app y FARO) — T-30 fase 2.
- GET /api/chat/reuniones/grabaciones            → mis grabaciones (soy el creador), con reunión, fecha, tamaño y enlace de
                                                    descarga del Drive (misma sesión). Lo que otros compartan conmigo se ve
                                                    en el Drive («Compartidos conmigo»), no aquí.
- GET /api/chat/reuniones/<rid>/grabaciones      → grabaciones de una reunión (solo su creador).
"""
from urllib.parse import quote

import psycopg2.extras
from flask import Blueprint, jsonify, request

from interfaces.api.reuniones_api import _yo, _conexion

bp_reuniones_grab = Blueprint('reuniones_grabaciones', __name__, url_prefix='/api/chat/reuniones')
DESCARGA = 'https://datos.maquita.com.ec/api/almacen/archivos/descargar?ruta='
DRIVE = 'https://datos.maquita.com.ec/archivos-almacen'


def _fila(g):
    carpeta = (g['ruta_drive'] or '').rsplit('/', 1)[0]
    return {'id': g['id'], 'reunion_id': g['reunion_id'], 'asunto': g['asunto'] or g['room'] or 'Reunión', 'sala': g['room'],
            'fecha': g['creado_en'].isoformat(timespec='minutes') if g['creado_en'] else None,
            'bytes': g['bytes'], 'ruta_drive': g['ruta_drive'], 'url_descarga': DESCARGA + quote(g['ruta_drive'] or ''),
            'url_drive': DRIVE + quote(carpeta), 'vence_en': g['vence_en'].date().isoformat() if g['vence_en'] else None,
            'conservar': bool(g['conservar'])}


@bp_reuniones_grab.route('/grabaciones', methods=['GET'])
def mis_grabaciones():
    yo = _yo()
    if not yo:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    try:
        limite = max(1, min(int(request.args.get('limit', 50)), 200))
    except ValueError:
        limite = 50
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""SELECT g.*, r.asunto FROM reuniones_grabaciones g LEFT JOIN reuniones_programadas r ON r.id = g.reunion_id
                       WHERE g.usuario_id = %s ORDER BY g.creado_en DESC LIMIT %s""", (yo['id'], limite))
        filas = [_fila(g) for g in cur.fetchall()]
    return jsonify({'success': True, 'grabaciones': filas})


@bp_reuniones_grab.route('/<int:rid>/grabaciones', methods=['GET'])
def de_reunion(rid):
    yo = _yo()
    if not yo:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""SELECT g.*, r.asunto FROM reuniones_grabaciones g JOIN reuniones_programadas r ON r.id = g.reunion_id
                       WHERE g.reunion_id = %s AND g.usuario_id = %s ORDER BY g.creado_en DESC""", (rid, yo['id']))
        filas = [_fila(g) for g in cur.fetchall()]
    return jsonify({'success': True, 'grabaciones': filas})
