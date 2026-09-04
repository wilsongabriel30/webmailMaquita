# -*- coding: utf-8 -*-
"""Reenviar, fijar/desfijar, marcar todo leído, fijados.
Extraído de controlador_chat.py (líneas 2622-2779) el 28/08/2026 sin cambios en las rutas. Las rutas se registran en
bp_chat al importar este módulo (lo hace controlador_chat.py, que sigue siendo el punto de entrada)."""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, servicio, autenticación…)

# =============================================================================
# REENVIO DE MENSAJES (Feature 2)
# =============================================================================

@bp_chat.route('/messages/<int:mensaje_id>/forward', methods=['POST'])
@requiere_autenticacion
def reenviar_mensaje(mensaje_id):
    """
    Reenvia un mensaje a otra conversacion.

    Request:
        { "conversation_id": int }
    """
    try:
        datos = request.get_json()
        conv_destino = datos.get('conversation_id')
        if not conv_destino:
            return jsonify({'success': False, 'mensaje': 'conversation_id requerido'}), 400

        servicio = obtener_servicio_chat()
        resultado = servicio.reenviar_mensaje(mensaje_id, obtener_usuario_id(), conv_destino)

        if resultado.exito and resultado.datos:
            from interfaces.websocket.manejador_websocket import emitir_mensaje_nuevo
            emitir_mensaje_nuevo(conv_destino, resultado.datos.get('mensaje', {}))

        return jsonify({
            'success': resultado.exito,
            'mensaje': resultado.mensaje
        }), 200 if resultado.exito else 400

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'mensaje': 'Error interno'}), 500


# =============================================================================
# MENSAJES FIJADOS (Feature 3)
# =============================================================================

def _conv_de_mensaje(mensaje_id):
    """Devuelve el conversation_id de un mensaje (o None)."""
    try:
        from sqlalchemy import text as _t
        ses = g.get("db_session_chat")
        if not ses:
            ses = obtener_gestor().session(); g.db_session_chat = ses
        fila = ses.execute(_t("SELECT conversation_id FROM chat_messages WHERE id = :id"), {"id": mensaje_id}).fetchone()
        return fila[0] if fila else None
    except Exception:
        return None


@bp_chat.route('/messages/<int:mensaje_id>/pin', methods=['POST'])
@requiere_autenticacion
def fijar_mensaje(mensaje_id):
    """Fija un mensaje en su conversacion."""
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.fijar_mensaje(mensaje_id, obtener_usuario_id())
        if resultado.exito:
            cid = _conv_de_mensaje(mensaje_id)
            if cid:
                try:
                    emitir_a_conversacion(cid, 'message_pinned', {'conversation_id': cid, 'message_id': mensaje_id, 'pinned': True})
                except Exception:
                    pass
        return jsonify({
            'success': resultado.exito,
            'mensaje': resultado.mensaje
        }), 200 if resultado.exito else 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'mensaje': 'Error interno'}), 500


@bp_chat.route('/messages/<int:mensaje_id>/pin', methods=['DELETE'])
@requiere_autenticacion
def desfijar_mensaje(mensaje_id):
    """Desfija un mensaje."""
    try:
        servicio = obtener_servicio_chat()
        cid = _conv_de_mensaje(mensaje_id)
        resultado = servicio.desfijar_mensaje(mensaje_id, obtener_usuario_id())
        if resultado.exito and cid:
            try:
                emitir_a_conversacion(cid, 'message_pinned', {'conversation_id': cid, 'message_id': mensaje_id, 'pinned': False})
            except Exception:
                pass
        return jsonify({
            'success': resultado.exito,
            'mensaje': resultado.mensaje
        }), 200 if resultado.exito else 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'mensaje': 'Error interno'}), 500


@bp_chat.route('/conversations/mark-all-read', methods=['POST'])
@requiere_autenticacion
def marcar_todo_leido():
    """Marca todas las conversaciones como leidas."""
    try:
        usuario_id = obtener_usuario_id()
        servicio = obtener_servicio_chat()
        resultado = servicio.listar_conversaciones(usuario_id)
        if resultado.exito:
            conversaciones = resultado.datos.get('conversaciones', [])
            for conv in conversaciones:
                no_leidos = conv.get('mensajes_no_leidos', 0) or conv.get('unread_count', 0)
                if no_leidos and no_leidos > 0:
                    conv_id = conv.get('id')
                    if conv_id:
                        servicio.marcar_leido(conv_id, usuario_id)
        if hasattr(g, 'db_session_chat') and g.db_session_chat:
            g.db_session_chat.commit()
        return jsonify({'success': True, 'mensaje': 'Todos marcados como leidos'}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'mensaje': 'Error interno'}), 500


@bp_chat.route('/conversations/<int:conversacion_id>/pinned', methods=['GET'])
@requiere_autenticacion
def obtener_mensajes_fijados(conversacion_id):
    """Obtiene los mensajes fijados de una conversacion."""
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.obtener_mensajes_fijados(conversacion_id, obtener_usuario_id())

        if resultado.exito and resultado.datos:
            # Map to frontend-friendly format
            pinned = []
            for m in resultado.datos.get('pinned', []):
                pinned.append({
                    'id': m.get('id'),
                    'content': m.get('contenido'),
                    'sender_id': m.get('remitente_id'),
                    'created_at': m.get('creado_en'),
                    'message_type': m.get('tipo')
                })
            return jsonify({'success': True, 'pinned': pinned}), 200

        return jsonify({
            'success': resultado.exito,
            'mensaje': resultado.mensaje,
            'pinned': []
        }), 200 if resultado.exito else 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'mensaje': 'Error interno', 'pinned': []}), 500

