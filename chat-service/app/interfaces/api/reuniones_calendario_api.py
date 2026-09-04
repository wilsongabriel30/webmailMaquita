# -*- coding: utf-8 -*-
"""
Un solo ecosistema reuniones ⇄ calendario (T-30): vínculo reunión ↔ evento del correo.
- POST /api/chat/reuniones/<rid>/calendario       → crea el evento del correo para una reunión existente (p. ej. creada
                                                     desde la web de FARO). Idempotente: si ya está vinculada, devuelve el id.
- POST /api/chat/reuniones/<rid>/vincular-evento  → {evento_id, calendar_id}: guarda el vínculo cuando el evento lo creó
                                                     el calendario del correo (marca X-MAQUITA-REUNION en su descripción).
- PUT  /api/chat/reuniones/<rid>                  → {asunto, inicio, duracion_horas, participantes, mensaje}: actualiza la
                                                     reunión y, si está vinculada, el evento del correo; avisa por T-03.
Solo el creador. Sesión del chat (JWT / chat_session).
"""
import json
from datetime import datetime, timedelta

import psycopg2.extras
from flask import Blueprint, jsonify, request

from interfaces.api.reuniones_api import _yo, _a_dict, _conexion, _evento_correo_crear, _participantes

bp_reuniones_vinculo = Blueprint('reuniones_vinculo', __name__, url_prefix='/api/chat/reuniones')


def _config(r):
    cfg = r.get('config_sala') or {}
    return json.loads(cfg) if isinstance(cfg, str) else dict(cfg)


def _fila_del_creador(rid, yo):
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT * FROM reuniones_programadas WHERE id = %s AND creador_id = %s", (rid, yo['id']))
        r = cur.fetchone()
    return dict(r) if r else None


@bp_reuniones_vinculo.route('/<int:rid>/calendario', methods=['POST'])
def crear_evento(rid):
    yo = _yo()
    if not yo:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    r = _fila_del_creador(rid, yo)
    if not r:
        return jsonify({'success': False, 'error': 'Solo el creador puede vincular la reunión'}), 403
    cfg = _config(r)
    if cfg.get('evento_correo'):
        return jsonify({'success': True, 'evento_correo': cfg['evento_correo'], 'ya_existia': True})
    ev = _evento_correo_crear(yo, r, r['asunto'], r['fecha_hora'], r['duracion_horas'] or 1,
                              _participantes(r['participantes_emails']), r['mensaje'] or '')
    return jsonify({'success': bool(ev), 'evento_correo': ev, 'ya_existia': False}), (200 if ev else 502)


@bp_reuniones_vinculo.route('/<int:rid>/vincular-evento', methods=['POST'])
def vincular(rid):
    yo = _yo()
    if not yo:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    d = request.get_json(silent=True) or {}
    if not d.get('evento_id'):
        return jsonify({'success': False, 'error': 'evento_id requerido'}), 400
    with _conexion() as con, con.cursor() as cur:
        cur.execute("""UPDATE reuniones_programadas SET config_sala = COALESCE(config_sala,'{}'::jsonb) || %s::jsonb, updated_at = NOW()
                       WHERE id = %s AND creador_id = %s RETURNING id""",
                    (json.dumps({'evento_correo': str(d['evento_id']), 'evento_correo_calendario': str(d.get('calendar_id') or ''),
                                 'origen': 'calendario'}), rid, yo['id']))
        ok = cur.fetchone() is not None
    return jsonify({'success': ok}), (200 if ok else 403)


@bp_reuniones_vinculo.route('/<int:rid>', methods=['PUT'])
def actualizar(rid):
    yo = _yo()
    if not yo:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    r = _fila_del_creador(rid, yo)
    if not r:
        return jsonify({'success': False, 'error': 'Solo el creador puede modificar la reunión'}), 403
    d = request.get_json(silent=True) or {}
    asunto = (d.get('asunto') or r['asunto'] or '').strip()[:200] or r['asunto']
    inicio = r['fecha_hora']
    if d.get('inicio'):
        try:
            inicio = datetime.fromisoformat(str(d['inicio']).replace('Z', ''))
        except ValueError:
            return jsonify({'success': False, 'error': 'inicio debe ser ISO-8601'}), 400
    try:
        duracion = max(1, min(int(d.get('duracion_horas', r['duracion_horas'] or 1)), 12))
    except (TypeError, ValueError):
        duracion = r['duracion_horas'] or 1
    participantes = sorted({str(p).strip().lower() for p in d.get('participantes', _participantes(r['participantes_emails'])) if str(p).strip()})
    mensaje = (d.get('mensaje') if d.get('mensaje') is not None else r['mensaje']) or ''
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""UPDATE reuniones_programadas SET asunto=%s, fecha_hora=%s, duracion_horas=%s, participantes_emails=%s,
                       mensaje=%s, updated_at=NOW() WHERE id=%s RETURNING *""",
                    (asunto, inicio, duracion, ', '.join(participantes), mensaje[:1000], rid))
        nuevo = dict(cur.fetchone())
    cfg = _config(nuevo)
    evento_ok = None
    if cfg.get('evento_correo') and not d.get('sin_calendario'):
        try:
            from interfaces.api.calendario_api import _correo
            _, err = _correo('PUT', f"/api/calendar/events/{cfg['evento_correo']}", json={
                'summary': asunto, 'dtstart': inicio.isoformat(), 'dtend': (inicio + timedelta(hours=duracion)).isoformat(),
                'attendees': participantes})
            evento_ok = err is None
        except Exception as e:
            print(f'[reuniones] actualizar evento del correo: {e}')
            evento_ok = False
    try:
        from interfaces.websocket.notificaciones_globales import emitir, usuarios_por_correo, avatar_usuario
        ids = [u for u in usuarios_por_correo(participantes) if u != yo['id']]
        if ids:
            emitir(ids, 'reunion', f'Reunión actualizada: {asunto}', f"{yo['nombre']} · {inicio:%d/%m %H:%M}",
                   f"https://mail.maquita.org/api/chat/reuniones/{rid}/acceso",
                   {'origen': 'reuniones', 'reunion_id': rid, 'sala': nuevo['nombre_sala'], 'inicio': inicio.isoformat(timespec='minutes'),
                    'avatar': avatar_usuario(yo['id']), 'actualizada': True})
    except Exception as e:
        print(f'[reuniones] aviso actualización: {e}')
    out = _a_dict(nuevo, yo)
    out['reunion_id'] = rid
    out['evento_correo'] = cfg.get('evento_correo')
    return jsonify({'success': True, 'reunion': out, 'evento_correo_actualizado': evento_ok})
