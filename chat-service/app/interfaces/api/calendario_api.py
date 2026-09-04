# -*- coding: utf-8 -*-
"""
Calendario del correo para el cliente Teams Maquita — T-05.
============================================================
El calendario VIVE en el servidor de correo (Radicale + API REST del webmail,
`https://mail.maquita.org/api/calendar/*`). Este módulo NO copia nada: consulta esa
API en nombre del usuario, con su propio JWT (`access_token`), y devuelve una
agenda normalizada en español. Si el correo no responde, se informa el error.

    GET  /api/chat/calendario/proximos?dias=7&limit=50   → agenda (propia + compartida)
    GET  /api/chat/calendario/hoy                        → sólo hoy
    GET  /api/chat/calendario/calendarios                → mis calendarios
    POST /api/chat/calendario/eventos                    → crear evento (en el calendario por defecto si no se indica)
"""
import os
from datetime import datetime, timedelta

import requests
from flask import Blueprint, jsonify, request, session

bp_calendario = Blueprint('calendario_chat', __name__, url_prefix='/api/chat/calendario')

CORREO_API = os.getenv('CORREO_API_URL', 'https://mail.maquita.org').rstrip('/')
URL_CALENDARIO = os.getenv('CORREO_URL_CALENDARIO', CORREO_API + '/calendar')
TIEMPO_ESPERA = 12


def _token():
    tok = request.cookies.get('access_token') or ''
    auth = request.headers.get('Authorization', '')
    if not tok and auth.startswith('Bearer '):
        tok = auth[7:]
    return tok or session.get('access_token') or ''


def _correo(metodo, ruta, **kw):
    tok = _token()
    if not tok:
        return None, (401, 'Se necesita el JWT del correo (cookie access_token) para consultar el calendario')
    try:
        r = requests.request(metodo, CORREO_API + ruta, cookies={'access_token': tok},
                             headers={'Accept': 'application/json'}, timeout=TIEMPO_ESPERA, **kw)
    except requests.RequestException as e:
        return None, (502, f'El servidor de correo no respondió: {e.__class__.__name__}')
    if r.status_code == 401:
        return None, (401, 'El correo rechazó el token (expirado): renovar con POST /api/auth/refresh')
    if r.status_code >= 400:
        return None, (502, f'Correo respondió {r.status_code}: {r.text[:200]}')
    if r.status_code == 204 or not r.content:
        return {}, None
    try:
        return r.json(), None
    except ValueError:
        return None, (502, 'Respuesta del correo no es JSON')


def _normalizar(ev, compartido=False):
    return {
        'id': ev.get('id'), 'uid': ev.get('uid'), 'titulo': ev.get('summary') or '(sin título)',
        'descripcion': ev.get('description') or '', 'lugar': ev.get('location') or '',
        'inicio': ev.get('dtstart'), 'fin': ev.get('dtend'), 'todo_el_dia': bool(ev.get('all_day')),
        'estado': ev.get('status') or 'confirmed', 'recurrente': bool(ev.get('rrule')),
        'calendario': ev.get('calendar_name') or '', 'calendario_id': ev.get('calendar_id'),
        'color': ev.get('color') or '', 'zona_horaria': ev.get('timezone') or 'America/Guayaquil',
        'asistentes': ev.get('attendees') or [], 'recordatorios': ev.get('reminders') or [],
        'compartido': compartido, 'url': URL_CALENDARIO,
    }


def _agenda(inicio, fin, limite):
    q = {'start': inicio.isoformat(timespec='seconds'), 'end': fin.isoformat(timespec='seconds')}
    propios, err = _correo('GET', '/api/calendar/events', params=q)
    if err:
        return None, err
    compartidos, err2 = _correo('GET', '/api/calendar/shared/events', params=q)
    eventos = [_normalizar(e) for e in (propios or [])] + [_normalizar(e, True) for e in (compartidos or [])]
    eventos.sort(key=lambda e: (e['inicio'] or ''))
    return eventos[:limite], None


def _error(err):
    codigo, msg = err
    return jsonify({'success': False, 'error': msg}), codigo


@bp_calendario.route('/proximos', methods=['GET'])
def proximos():
    try:
        dias = max(1, min(int(request.args.get('dias', 7)), 60))
        limite = max(1, min(int(request.args.get('limit', 50)), 200))
    except ValueError:
        dias, limite = 7, 50
    ahora = datetime.now()
    inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    eventos, err = _agenda(inicio, inicio + timedelta(days=dias), limite)
    if err:
        return _error(err)
    return jsonify({'success': True, 'desde': inicio.isoformat(timespec='minutes'), 'dias': dias,
                    'ahora': ahora.isoformat(timespec='minutes'), 'eventos': eventos, 'fuente': CORREO_API})


@bp_calendario.route('/hoy', methods=['GET'])
def hoy():
    inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    eventos, err = _agenda(inicio, inicio + timedelta(days=1), 100)
    if err:
        return _error(err)
    return jsonify({'success': True, 'fecha': inicio.date().isoformat(), 'eventos': eventos})


@bp_calendario.route('/calendarios', methods=['GET'])
def calendarios():
    datos, err = _correo('GET', '/api/calendar/calendars')
    if err:
        return _error(err)
    return jsonify({'success': True, 'calendarios': [
        {'id': c.get('id'), 'nombre': c.get('name'), 'color': c.get('color'), 'por_defecto': bool(c.get('is_default')),
         'zona_horaria': c.get('timezone')} for c in (datos or [])]})


@bp_calendario.route('/eventos', methods=['POST'])
def crear_evento():
    d = request.get_json(silent=True) or {}
    if not d.get('titulo') or not d.get('inicio'):
        return jsonify({'success': False, 'error': 'titulo e inicio son obligatorios'}), 400
    try:
        inicio = datetime.fromisoformat(str(d['inicio']).replace('Z', ''))
        fin = datetime.fromisoformat(str(d['fin']).replace('Z', '')) if d.get('fin') else inicio + timedelta(hours=1)
    except ValueError:
        return jsonify({'success': False, 'error': 'inicio/fin deben ser ISO-8601'}), 400
    cal_id = d.get('calendario_id')
    if not cal_id:
        cals, err = _correo('GET', '/api/calendar/calendars')
        if err:
            return _error(err)
        por_defecto = [c for c in (cals or []) if c.get('is_default')] or (cals or [])
        if not por_defecto:
            return jsonify({'success': False, 'error': 'El usuario no tiene calendarios en el correo'}), 404
        cal_id = por_defecto[0]['id']
    cuerpo = {'calendar_id': cal_id, 'summary': d['titulo'][:200], 'description': d.get('descripcion', '')[:2000],
              'location': d.get('lugar', '')[:200], 'dtstart': inicio.isoformat(), 'dtend': fin.isoformat(),
              'all_day': bool(d.get('todo_el_dia')), 'timezone': d.get('zona_horaria', 'America/Guayaquil'),
              'reminders': d.get('recordatorios', []), 'attendees': d.get('asistentes', [])}
    ev, err = _correo('POST', '/api/calendar/events', json=cuerpo)
    if err:
        return _error(err)
    return jsonify({'success': True, 'evento': _normalizar(ev)}), 201
