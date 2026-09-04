# -*- coding: utf-8 -*-
"""
API de reuniones (Meet Maquita / Jitsi) para el cliente Teams Maquita — T-04.
==============================================================================
Misma tabla que el módulo /reuniones/ de FARO (`reuniones_programadas`, BD nomina):
lo que se crea aquí aparece en FARO y viceversa. JWT de Jitsi generado al momento de
entrar (nunca se entregan tokens viejos).

    GET  /api/chat/reuniones/proximas?limit=20      → mis próximas reuniones
    POST /api/chat/reuniones                        → agendar
    POST /api/chat/reuniones/instantanea            → sala ahora mismo
    GET  /api/chat/reuniones/<id>/acceso            → URL + JWT fresco para entrar
    POST /api/chat/reuniones/<id>/cancelar          → solo el creador
"""
import json
import os
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
from flask import Blueprint, jsonify, request, session

from aplicacion.servicios.jitsi_jwt import generar_jwt, nombre_sala_nuevo, limpiar_nombre_sala, url_sala, url_sala_app, JITSI_URL

bp_reuniones = Blueprint('reuniones_chat', __name__, url_prefix='/api/chat/reuniones')


def _conexion():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def _yo():
    uid = session.get('usuario_id')
    if not uid:
        return None
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT id, COALESCE(NULLIF(TRIM(full_name), ''), username, email) AS nombre, lower(email) AS email, "
                    "profile_picture FROM usuarios WHERE id = %s", (uid,))
        return cur.fetchone()


def _es_app():
    """La app de escritorio pide la URL «modo app» con ?cliente=app o por su User-Agent (MaquitaTeams)."""
    return request.args.get('cliente') == 'app' or 'MaquitaTeams' in (request.headers.get('User-Agent') or '')


def _participantes(csv):
    return [e.strip().lower() for e in (csv or '').split(',') if e.strip()]


def _a_dict(r, yo):
    inicio = r['fecha_hora']
    dur = r['duracion_horas'] or 1
    return {
        'id': r['id'], 'asunto': r['asunto'] or 'Reunión Maquita Meet', 'sala': r['nombre_sala'],
        'inicio': inicio.isoformat(timespec='minutes') if inicio else None,
        'fin': (inicio + timedelta(hours=dur)).isoformat(timespec='minutes') if inicio else None,
        'duracion_horas': dur, 'estado': r['estado'], 'es_creador': r['creador_id'] == yo['id'],
        'creador_id': r['creador_id'], 'participantes': _participantes(r['participantes_emails']),
        'mensaje': r['mensaje'] or '', 'config': r['config_sala'] or {},
        'url_sala': url_sala(r['nombre_sala']),
        'url_acceso': f"https://mail.maquita.org/api/chat/reuniones/{r['id']}/acceso",
    }


def _evento_correo_crear(yo, fila, asunto, inicio, duracion, participantes, mensaje):
    """Refleja la reunión agendada en el calendario del CORREO del creador (con invitación a los
    participantes). Un solo cliente, un solo calendario. Devuelve el id del evento o None."""
    try:
        from interfaces.api.calendario_api import _correo
        cals, err = _correo('GET', '/api/calendar/calendars')
        if err:
            return None
        por_defecto = [c for c in (cals or []) if c.get('is_default')] or (cals or [])
        if not por_defecto:
            return None
        cuerpo = {
            'calendar_id': por_defecto[0]['id'], 'summary': asunto,
            'description': (mensaje + '\n\n' if mensaje else '') + 'Meet Maquita: ' + url_sala(fila['nombre_sala']) +
                           f"\nEntrar con tu usuario: https://mail.maquita.org/api/chat/reuniones/{fila['id']}/acceso?redirigir=1",
            'location': url_sala(fila['nombre_sala']), 'dtstart': inicio.isoformat(), 'dtend': (inicio + timedelta(hours=duracion)).isoformat(),
            'all_day': False, 'timezone': 'America/Guayaquil', 'reminders': [{'minutes': 10}], 'attendees': list(participantes),
        }
        ev, err = _correo('POST', '/api/calendar/events', json=cuerpo)
        if err or not ev:
            return None
        with _conexion() as con, con.cursor() as cur:
            cur.execute("UPDATE reuniones_programadas SET config_sala = COALESCE(config_sala,'{}'::jsonb) || %s::jsonb WHERE id = %s",
                        (json.dumps({'evento_correo': ev.get('id'), 'evento_correo_calendario': por_defecto[0]['id']}), fila['id']))
        return ev.get('id')
    except Exception as e:
        print(f'[reuniones] calendario del correo: {e}')
        return None


def _evento_correo_eliminar(fila):
    try:
        cfg = fila.get('config_sala') or {}
        if isinstance(cfg, str):
            cfg = json.loads(cfg)
        eid = cfg.get('evento_correo')
        if not eid:
            return False
        from interfaces.api.calendario_api import _correo
        _, err = _correo('DELETE', f'/api/calendar/events/{eid}')
        return err is None
    except Exception:
        return False


def _fila_reunion(cur, rid, yo):
    cur.execute("""SELECT * FROM reuniones_programadas WHERE id = %s
                   AND (creador_id = %s OR lower(participantes_emails) LIKE %s)""",
                (rid, yo['id'], f"%{yo['email']}%"))
    return cur.fetchone()


@bp_reuniones.route('/proximas', methods=['GET'])
def proximas():
    yo = _yo()
    if not yo:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    try:
        limite = max(1, min(int(request.args.get('limit', 20)), 100))
    except ValueError:
        limite = 20
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""SELECT * FROM reuniones_programadas
                       WHERE (creador_id = %s OR lower(participantes_emails) LIKE %s)
                         AND estado <> 'cancelada'
                         AND fecha_hora + (COALESCE(duracion_horas,1) || ' hours')::interval >= NOW()
                       ORDER BY fecha_hora ASC LIMIT %s""", (yo['id'], f"%{yo['email']}%", limite))
        filas = cur.fetchall()
    ahora = datetime.now()
    items = []
    for r in filas:
        d = _a_dict(r, yo)
        d['en_curso'] = bool(r['fecha_hora'] and r['fecha_hora'] <= ahora)
        # T-30: identidad única con el calendario del correo
        d['reunion_id'] = r['id']
        _cfg = r['config_sala'] or {}
        _cfg = json.loads(_cfg) if isinstance(_cfg, str) else _cfg
        d['evento_correo'] = _cfg.get('evento_correo')
        items.append(d)
    return jsonify({'success': True, 'reuniones': items, 'ahora': ahora.isoformat(timespec='minutes')})


def _crear(yo, asunto, inicio, duracion, participantes, mensaje, config, sala):
    sala = limpiar_nombre_sala(sala) if sala else nombre_sala_nuevo()
    tok_mod = generar_jwt(yo['id'], yo['nombre'], yo['email'], sala, True, max(duracion, 8))
    tok_inv = generar_jwt(0, 'Invitado', 'invitado@maquita.com.ec', sala, False, max(duracion, 8))
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""INSERT INTO reuniones_programadas
            (asunto, nombre_sala, fecha_hora, duracion_horas, creador_id, enlace_moderador, enlace_invitado,
             token_moderador, token_invitado, participantes_emails, mensaje, config_sala, estado, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'programada',NOW(),NOW()) RETURNING *""",
            (asunto, sala, inicio, duracion, yo['id'], url_sala(sala, tok_mod), url_sala(sala),
             tok_mod, tok_inv, ', '.join(participantes), mensaje, json.dumps(config or {})))
        fila = cur.fetchone()
    # Aviso inmediato a los participantes internos por el canal único (T-03)
    try:
        from interfaces.websocket.notificaciones_globales import emitir, usuarios_por_correo, avatar_usuario
        ids = [u for u in usuarios_por_correo(participantes) if u != yo['id']]
        if ids:
            emitir(ids, 'reunion', f'Reunión: {asunto}',
                   f"{yo['nombre']} te invitó · {inicio:%d/%m %H:%M}",
                   f"https://mail.maquita.org/api/chat/reuniones/{fila['id']}/acceso",
                   {'origen': 'reuniones', 'reunion_id': fila['id'], 'sala': sala, 'inicio': inicio.isoformat(timespec='minutes'),
                    'avatar': avatar_usuario(yo['id'])})
    except Exception as e:
        print(f'[reuniones] aviso: {e}')
    return fila


@bp_reuniones.route('', methods=['POST'])
def crear():
    yo = _yo()
    if not yo:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    d = request.get_json(silent=True) or {}
    asunto = (d.get('asunto') or '').strip()[:200] or 'Reunión Maquita Meet'
    try:
        inicio = datetime.fromisoformat(str(d.get('inicio', '')).replace('Z', ''))
    except ValueError:
        return jsonify({'success': False, 'error': 'inicio debe ser ISO-8601, p. ej. 2026-08-28T10:00'}), 400
    try:
        duracion = max(1, min(int(d.get('duracion_horas', 1)), 12))
    except (TypeError, ValueError):
        duracion = 1
    participantes = sorted({str(p).strip().lower() for p in d.get('participantes', []) if str(p).strip()})
    fila = _crear(yo, asunto, inicio, duracion, participantes, (d.get('mensaje') or '')[:1000],
                  d.get('config') if isinstance(d.get('config'), dict) else {}, d.get('nombre_sala'))
    evento = None
    if d.get('calendario', True):
        evento = _evento_correo_crear(yo, fila, asunto, inicio, duracion, participantes, (d.get('mensaje') or '')[:1000])
    r = _a_dict(fila, yo)
    r['evento_correo'] = evento
    return jsonify({'success': True, 'reunion': r}), 201


@bp_reuniones.route('/instantanea', methods=['POST'])
def instantanea():
    yo = _yo()
    if not yo:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    d = request.get_json(silent=True) or {}
    asunto = (d.get('asunto') or '').strip()[:200] or f"Reunión de {yo['nombre']}"
    participantes = sorted({str(p).strip().lower() for p in d.get('participantes', []) if str(p).strip()})
    inicio = datetime.now().replace(second=0, microsecond=0)
    fila = _crear(yo, asunto, inicio, 2, participantes, '', {'sin_lobby': True}, None)
    # También en el calendario del correo (igual que las agendadas), salvo "calendario": false
    evento = _evento_correo_crear(yo, fila, asunto, inicio, 2, participantes, '') if d.get('calendario', True) else None
    tok = generar_jwt(yo['id'], yo['nombre'], yo['email'], fila['nombre_sala'], True, 8, yo['profile_picture'])
    r = _a_dict(fila, yo)
    r['evento_correo'] = evento
    url_web = url_sala(fila['nombre_sala'], tok, True)
    url_app = url_sala_app(fila['nombre_sala'], tok, True)
    r.update({'jwt': tok, 'url': url_app if _es_app() else url_web, 'url_web': url_web, 'url_app': url_app, 'moderador': True,
              'expira': (datetime.now() + timedelta(hours=8)).isoformat(timespec='minutes')})
    return jsonify({'success': True, 'reunion': r}), 201


@bp_reuniones.route('/<int:rid>/acceso', methods=['GET'])
def acceso(rid):
    yo = _yo()
    if not yo:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        r = _fila_reunion(cur, rid, yo)
    if not r:
        return jsonify({'success': False, 'error': 'Reunión no encontrada o sin acceso'}), 404
    if r['estado'] == 'cancelada':
        return jsonify({'success': False, 'error': 'La reunión fue cancelada'}), 410
    es_creador = r['creador_id'] == yo['id']
    horas = max(r['duracion_horas'] or 8, 8)
    tok = generar_jwt(yo['id'], yo['nombre'], yo['email'], r['nombre_sala'], es_creador, horas, yo['profile_picture'])
    url_web = url_sala(r['nombre_sala'], tok, es_creador)
    url_app = url_sala_app(r['nombre_sala'], tok, es_creador, camara_al_entrar=request.args.get('camara', '1') != '0')
    url = url_app if _es_app() else url_web
    if request.args.get('redirigir') == '1':
        from flask import redirect
        return redirect(url)
    return jsonify({'success': True, 'id': rid, 'sala': r['nombre_sala'], 'url': url, 'url_web': url_web, 'url_app': url_app, 'jwt': tok,
                    'moderador': es_creador, 'expira': (datetime.now() + timedelta(hours=horas)).isoformat(timespec='minutes'),
                    'dominio': JITSI_URL})


@bp_reuniones.route('/<int:rid>/cancelar', methods=['POST'])
def cancelar(rid):
    yo = _yo()
    if not yo:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("UPDATE reuniones_programadas SET estado='cancelada', updated_at=NOW() "
                    "WHERE id=%s AND creador_id=%s RETURNING *", (rid, yo['id']))
        r = cur.fetchone()
    if not r:
        return jsonify({'success': False, 'error': 'Solo el creador puede cancelar'}), 403
    evento_eliminado = _evento_correo_eliminar(dict(r))
    try:
        from interfaces.websocket.notificaciones_globales import emitir, usuarios_por_correo
        ids = [u for u in usuarios_por_correo(_participantes(r['participantes_emails'])) if u != yo['id']]
        if ids:
            emitir(ids, 'reunion', f"Reunión cancelada: {r['asunto']}", f"{yo['nombre']} canceló la reunión",
                   'https://mail.maquita.org/chat/', {'origen': 'reuniones', 'reunion_id': rid, 'cancelada': True})
    except Exception:
        pass
    return jsonify({'success': True, 'reunion': _a_dict(r, yo), 'evento_correo_eliminado': evento_eliminado})
