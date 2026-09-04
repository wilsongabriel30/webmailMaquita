# -*- coding: utf-8 -*-
"""Grabación de llamadas (LiveKit Egress).
Extraído de controlador_chat.py (líneas 3031-3253) el 28/08/2026 sin cambios en las rutas. Las rutas se registran en
bp_chat al importar este módulo (lo hace controlador_chat.py, que sigue siendo el punto de entrada)."""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, servicio, autenticación…)
from interfaces.api.chat_llamadas import _livekit_jwt

# =============================================================================
# GRABACION DE LLAMADAS/CONFERENCIAS (LiveKit Egress en CT 210)
# El egress compone la sala y escribe un MP4 en /var/livekit/grabaciones,
# servido por nginx interno (8081) SOLO a esta VM. FARO lo entrega con auth.
# Tabla: chat_grabaciones. Doc: livekit-servidor-llamadas-chat-20260612.md
# =============================================================================

def _egress_twirp(metodo: str, cuerpo: dict):
    """Llama un metodo del servicio Egress de LiveKit. Devuelve (ok, data|error)."""
    import os
    import json as _json
    import time as _time
    import urllib.request

    api_key = os.environ.get('LIVEKIT_API_KEY')
    api_secret = os.environ.get('LIVEKIT_API_SECRET')
    api_url = os.environ.get('LIVEKIT_API_URL', 'http://193.16.0.27:7880')
    if not api_key or not api_secret:
        return False, 'LiveKit no configurado'

    ahora = int(_time.time())
    token = _livekit_jwt(api_key, api_secret, {
        'iss': api_key, 'nbf': ahora - 10, 'exp': ahora + 600,
        'video': {'roomRecord': True},
    })
    req = urllib.request.Request(
        f'{api_url}/twirp/livekit.Egress/{metodo}',
        data=_json.dumps(cuerpo).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return True, _json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            err = _json.loads(e.read()).get('msg', str(e))
        except Exception:
            err = f'HTTP {e.code}'
        return False, err
    except Exception as e:
        return False, str(e)


def _usuario_en_sala(room: str, usuario_id: int) -> bool:
    """True si el usuario puede operar/ver una sala (participante de la llamada 1-1
    o cualquier autenticado en conferencias)."""
    if room.startswith('llamada_'):
        partes = room.split('_')[1:]
        return str(usuario_id) in partes
    return room.startswith('conf_')  # conferencias: cualquier participante autenticado


@bp_chat.route('/grabacion/iniciar', methods=['POST'])
@requiere_autenticacion
def iniciar_grabacion():
    """Inicia la grabacion de una sala. Body: { room }."""
    import re as _re
    import time as _time
    from sqlalchemy import text as _text

    usuario_id = obtener_usuario_id()
    datos = request.get_json(silent=True) or {}
    room = (datos.get('room') or '').strip()

    if not room or not _re.match(r'^[a-zA-Z0-9_\-]+$', room) or len(room) > 100:
        return jsonify({'exito': False, 'error': 'Sala invalida'}), 400
    if not _usuario_en_sala(room, usuario_id):
        return jsonify({'exito': False, 'error': 'No autorizado'}), 403

    archivo = f'{room}_{int(_time.time())}.mp4'
    ok, data = _egress_twirp('StartRoomCompositeEgress', {
        'room_name': room,
        'layout': 'grid',
        'file_outputs': [{'file_type': 'MP4', 'filepath': f'/out/{archivo}'}],
    })
    if not ok:
        return jsonify({'exito': False, 'error': f'No se pudo iniciar la grabacion: {data}'}), 502

    egress_id = data.get('egress_id')
    conversation_id = None
    if room.startswith('llamada_'):
        try:
            otro = [int(x) for x in room.split('_')[1:]]
        except ValueError:
            otro = []
        # conv no determinable aqui; queda null (se asocia por el room)

    db_session = g.get('db_session_chat')
    if not db_session:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session
    _conv = datos.get('conv') or datos.get('conversation_id')
    try:
        _conv = int(_conv) if _conv not in (None, '') else None
    except (TypeError, ValueError):
        _conv = None
    db_session.execute(_text("""
        INSERT INTO chat_grabaciones (room, egress_id, archivo, solicitante_id, estado, conversation_id)
        VALUES (:room, :eid, :arch, :uid, 'grabando', :conv)
    """), {'room': room, 'eid': egress_id, 'arch': archivo, 'uid': usuario_id, 'conv': _conv})
    db_session.commit()

    return jsonify({'exito': True, 'egress_id': egress_id, 'archivo': archivo}), 200


@bp_chat.route('/grabacion/detener', methods=['POST'])
@requiere_autenticacion
def detener_grabacion():
    """Detiene la grabacion. Body: { egress_id }."""
    from sqlalchemy import text as _text

    usuario_id = obtener_usuario_id()
    datos = request.get_json(silent=True) or {}
    egress_id = (datos.get('egress_id') or '').strip()
    if not egress_id:
        return jsonify({'exito': False, 'error': 'egress_id requerido'}), 400

    ok, data = _egress_twirp('StopEgress', {'egress_id': egress_id})
    # Aunque el stop falle (ya terminado), marcamos completada
    db_session = g.get('db_session_chat')
    if not db_session:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session
    db_session.execute(_text("""
        UPDATE chat_grabaciones SET estado = 'completada'
        WHERE egress_id = :eid
    """), {'eid': egress_id})
    db_session.commit()
    # T-30 fase 2: la grabación va al Drive del solicitante (compartida con los participantes) en segundo plano
    try:
        from interfaces.api.grabaciones_drive import programar_a_drive
        programar_a_drive(egress_id)
    except Exception as _e:
        print(f'[grabaciones] no se pudo programar: {_e}')

    return jsonify({'exito': True}), 200


@bp_chat.route('/grabacion/listar', methods=['GET'])
@requiere_autenticacion
def listar_grabaciones():
    """Grabaciones que el usuario solicito o de sus llamadas 1-1, recientes primero."""
    from sqlalchemy import text as _text

    usuario_id = obtener_usuario_id()
    db_session = g.get('db_session_chat')
    if not db_session:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session

    filas = db_session.execute(_text("""
        SELECT id, room, archivo, estado, creado_en, solicitante_id
        FROM chat_grabaciones
        WHERE solicitante_id = :uid
           OR room LIKE 'llamada_%' AND ('_' || :uid || '_') LIKE ('%_' || :uid || '_%')
        ORDER BY creado_en DESC
        LIMIT 100
    """), {'uid': usuario_id}).fetchall()

    grabaciones = []
    for f in filas:
        room = f[1]
        # filtro fino para llamadas 1-1: el usuario debe ser uno de los dos
        if room.startswith('llamada_') and str(usuario_id) not in room.split('_')[1:] and f[5] != usuario_id:
            continue
        grabaciones.append({
            'id': f[0],
            'room': room,
            'archivo': f[2],
            'estado': f[3],
            'creado_en': f[4].isoformat() if f[4] else None,
            'es_conferencia': room.startswith('conf_'),
        })
    return jsonify({'exito': True, 'grabaciones': grabaciones}), 200


@bp_chat.route('/grabacion/descargar/<int:grab_id>', methods=['GET'])
@requiere_autenticacion
def descargar_grabacion(grab_id: int):
    """Entrega el MP4 (stream desde el nginx interno del CT 210, con auth FARO)."""
    import os
    import urllib.request
    from flask import Response, stream_with_context
    from sqlalchemy import text as _text

    usuario_id = obtener_usuario_id()
    db_session = g.get('db_session_chat')
    if not db_session:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session

    fila = db_session.execute(_text("""
        SELECT room, archivo, solicitante_id FROM chat_grabaciones WHERE id = :id
    """), {'id': grab_id}).fetchone()
    if not fila:
        return jsonify({'exito': False, 'error': 'No encontrada'}), 404

    room, archivo, solicitante_id = fila[0], fila[1], fila[2]
    if solicitante_id != usuario_id and not _usuario_en_sala(room, usuario_id):
        return jsonify({'exito': False, 'error': 'No autorizado'}), 403

    base = os.environ.get('LIVEKIT_GRABACIONES_URL', 'http://193.16.0.27:8081')
    try:
        upstream = urllib.request.urlopen(f'{base}/{archivo}', timeout=20)
    except Exception:
        return jsonify({'exito': False, 'error': 'La grabacion aun no esta disponible'}), 404

    def generar():
        while True:
            trozo = upstream.read(65536)
            if not trozo:
                break
            yield trozo

    return Response(stream_with_context(generar()), mimetype='video/mp4', headers={
        'Content-Disposition': f'attachment; filename="{archivo}"'
    })

