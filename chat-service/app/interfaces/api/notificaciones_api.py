# -*- coding: utf-8 -*-
"""
API REST del canal de notificaciones (Teams Maquita, T-03).
    POST /api/chat/notificaciones          → otros sistemas (FARO, reuniones, calendario) empujan avisos.
                                             Cabecera X-Notif-Secret = NOTIF_SECRET (.env). Sin sesión.
    POST /api/chat/notificaciones/prueba   → el usuario autenticado se envía un aviso a sí mismo
                                             (para que el cliente valide su suscripción).
"""
import hmac
import os

from flask import Blueprint, jsonify, request, session

from interfaces.websocket.notificaciones_globales import emitir, usuarios_por_correo

bp_notificaciones = Blueprint('notificaciones_chat', __name__, url_prefix='/api/chat/notificaciones')


@bp_notificaciones.route('', methods=['POST'])
def empujar():
    secreto = os.getenv('NOTIF_SECRET', '')
    recibido = request.headers.get('X-Notif-Secret', '')
    if not secreto or not hmac.compare_digest(secreto, recibido):
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    d = request.get_json(silent=True) or {}
    ids = [int(u) for u in d.get('usuario_ids', []) if str(u).isdigit()]
    ids += usuarios_por_correo(d.get('correos', []))
    if not ids:
        return jsonify({'success': False, 'error': 'Falta usuario_ids o correos'}), 400
    if not d.get('titulo'):
        return jsonify({'success': False, 'error': 'Falta titulo'}), 400
    extra = {k: v for k, v in d.items() if k not in ('usuario_ids', 'correos', 'tipo', 'titulo', 'texto', 'url')}
    n = emitir(ids, d.get('tipo', 'sistema'), d['titulo'], d.get('texto', ''), d.get('url'), extra or None)
    return jsonify({'success': True, 'destinatarios': n})


@bp_notificaciones.route('/prueba', methods=['POST'])
def prueba():
    uid = session.get('usuario_id')
    if not uid:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    d = request.get_json(silent=True) or {}
    n = emitir([uid], d.get('tipo', 'sistema'), d.get('titulo', 'Prueba de notificaciones'),
               d.get('texto', 'Si ves esto, tu cliente está suscrito correctamente.'), d.get('url'),
               {'origen': 'prueba'})
    return jsonify({'success': True, 'destinatarios': n, 'usuario_id': uid})
