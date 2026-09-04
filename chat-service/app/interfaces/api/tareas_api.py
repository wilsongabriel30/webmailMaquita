# -*- coding: utf-8 -*-
"""
Tareas del correo para el cliente Teams Maquita — T-15.
========================================================
Las tareas viven en el correo (`https://mail.maquita.org/api/tasks/*`). Igual que el calendario,
este módulo NO copia nada: consulta esa API con el JWT del usuario y devuelve una vista unificada
en español para el riel de la app («Tareas» con contador).

    GET   /api/chat/tareas/pendientes?limit=100   → Mi día + Planificadas + Importantes (sin duplicados, sin completadas)
    GET   /api/chat/tareas/listas                 → listas del usuario
    POST  /api/chat/tareas                        → crear tarea rápida {titulo, vence?, importante?, mi_dia?, lista_id?}
    PATCH /api/chat/tareas/<id>/completar         → alternar completada
"""
from datetime import datetime

from flask import Blueprint, jsonify, request

from interfaces.api.calendario_api import _correo, _error, CORREO_API

bp_tareas = Blueprint('tareas_chat', __name__, url_prefix='/api/chat/tareas')
URL_TAREAS = CORREO_API + '/webmail/tasks'


def _normalizar(t):
    return {
        'id': t.get('id'), 'lista_id': t.get('list_id'), 'titulo': t.get('title') or '(sin título)',
        'descripcion': t.get('description') or '', 'nota': t.get('note') or '',
        'vence': t.get('due_date'), 'recordatorio': t.get('reminder'), 'prioridad': t.get('priority') or 'medium',
        'etiquetas': t.get('labels') or [], 'completada': bool(t.get('completed')), 'importante': bool(t.get('important')),
        'mi_dia': bool(t.get('my_day')), 'asignada_a': t.get('assigned_to'), 'creada_por': t.get('created_by'),
        'recurrencia': t.get('recurrence'), 'creada': t.get('created_at'), 'actualizada': t.get('updated_at'),
        'url': URL_TAREAS,
    }


@bp_tareas.route('/pendientes', methods=['GET'])
def pendientes():
    try:
        limite = max(1, min(int(request.args.get('limit', 100)), 500))
    except ValueError:
        limite = 100
    vistas = {}
    for nombre, ruta in (('mi_dia', '/api/tasks/views/my-day'), ('planificadas', '/api/tasks/views/planned'),
                         ('importantes', '/api/tasks/views/important'), ('asignadas', '/api/tasks/views/assigned')):
        datos, err = _correo('GET', ruta)
        if err:
            return _error(err)
        vistas[nombre] = datos or []
    unicas = {}
    for lista in vistas.values():
        for t in lista:
            if t.get('id') and not t.get('completed'):
                unicas[t['id']] = _normalizar(t)
    tareas = sorted(unicas.values(), key=lambda x: (x['vence'] is None, x['vence'] or '', not x['importante']))[:limite]
    hoy = datetime.now().date().isoformat()
    vencidas = sum(1 for t in tareas if t['vence'] and t['vence'][:10] < hoy)
    return jsonify({'success': True, 'total': len(tareas), 'vencidas': vencidas,
                    'mi_dia': len([t for t in vistas['mi_dia'] if not t.get('completed')]),
                    'importantes': len([t for t in vistas['importantes'] if not t.get('completed')]),
                    'tareas': tareas, 'fuente': CORREO_API, 'url': URL_TAREAS})


@bp_tareas.route('/listas', methods=['GET'])
def listas():
    datos, err = _correo('GET', '/api/tasks/lists')
    if err:
        return _error(err)
    return jsonify({'success': True, 'listas': [
        {'id': l.get('id'), 'nombre': l.get('name'), 'color': l.get('color'), 'tipo': l.get('list_type'),
         'icono': l.get('icon'), 'tareas': l.get('task_count', 0)} for l in (datos or [])]})


@bp_tareas.route('', methods=['POST'])
def crear():
    d = request.get_json(silent=True) or {}
    titulo = (d.get('titulo') or d.get('title') or '').strip()[:200]
    if not titulo:
        return jsonify({'success': False, 'error': 'titulo es obligatorio'}), 400
    lista_id = d.get('lista_id')
    if not lista_id:
        ls, err = _correo('GET', '/api/tasks/lists')
        if err:
            return _error(err)
        if not ls:
            return jsonify({'success': False, 'error': 'El usuario no tiene listas de tareas en el correo'}), 404
        lista_id = ls[0]['id']
    cuerpo = {'title': titulo, 'description': (d.get('descripcion') or '')[:2000], 'priority': d.get('prioridad', 'medium'),
              'important': bool(d.get('importante')), 'my_day': bool(d.get('mi_dia')), 'labels': d.get('etiquetas', [])}
    if d.get('vence'):
        cuerpo['due_date'] = d['vence']
    if d.get('recordatorio'):
        cuerpo['reminder'] = d['recordatorio']
    t, err = _correo('POST', f'/api/tasks/lists/{lista_id}/tasks', json=cuerpo)
    if err:
        return _error(err)
    return jsonify({'success': True, 'tarea': _normalizar(t)}), 201


@bp_tareas.route('/<tarea_id>/completar', methods=['PATCH', 'POST'])
def completar(tarea_id):
    t, err = _correo('PATCH', f'/api/tasks/tasks/{tarea_id}/toggle')
    if err:
        return _error(err)
    return jsonify({'success': True, 'tarea': _normalizar(t)})
