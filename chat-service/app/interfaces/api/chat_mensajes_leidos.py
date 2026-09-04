# -*- coding: utf-8 -*-
"""Mensajes: marcar conversación como leída.
Extraído de chat_mensajes.py (líneas 759-829) el 28/08/2026 sin cambios en las rutas; se registran en bp_chat al importarlo
(lo hace chat_mensajes.py, que sigue siendo el punto de entrada de mensajes)."""
from interfaces.api.chat_base import *  # noqa: F401,F403


@bp_chat.route('/conversations/<int:conversacion_id>/read', methods=['POST'])
@requiere_autenticacion
def marcar_leido(conversacion_id: int):
    """
    Marca mensajes como leidos.

    Request (opcional):
        {
            "hasta_mensaje_id": int
        }

    Response:
        {
            "exito": true,
            "mensaje": "Marcado como leido"
        }
    """
    try:
        # Usar silent=True para evitar error si no hay JSON
        datos = request.get_json(silent=True) or {}
        hasta_mensaje_id = datos.get('hasta_mensaje_id')

        servicio = obtener_servicio_chat()
        resultado = servicio.marcar_leido(
            conversacion_id=conversacion_id,
            usuario_id=obtener_usuario_id(),
            hasta_mensaje_id=hasta_mensaje_id
        )

        # Avisar a los DEMAS participantes (vistos azules en tiempo real).
        # Se emite a los rooms user_<id> de los otros, NO al lector (si no,
        # el lector marcaria como leidos sus propios mensajes enviados).
        if resultado.exito:
            try:
                from sqlalchemy import text as _text
                db_session = g.get('db_session_chat')
                if not db_session:
                    gestor = obtener_gestor()
                    db_session = gestor.session()
                    g.db_session_chat = db_session
                otros = db_session.execute(_text(
                    "SELECT user_id FROM chat_participants "
                    "WHERE conversation_id = :c AND user_id <> :u AND is_active = TRUE"
                ), {'c': conversacion_id, 'u': obtener_usuario_id()}).fetchall()
                from interfaces.websocket import manejador_websocket as _ws
                if _ws.socketio:
                    payload = {
                        'conversation_id': conversacion_id,
                        'hasta_mensaje_id': hasta_mensaje_id,
                        'reader_id': obtener_usuario_id()
                    }
                    for fila in otros:
                        _ws.socketio.emit('messages_read', payload, room=f"user_{fila[0]}")
            except Exception:
                pass

        return jsonify({
            'exito': resultado.exito,
            'mensaje': resultado.mensaje
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500
