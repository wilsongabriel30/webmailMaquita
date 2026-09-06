# -*- coding: utf-8 -*-
"""Reacciones a mensajes.
Extraído de controlador_chat.py (líneas 1690-1858) el 28/08/2026 sin cambios en las rutas. Las rutas se registran en
bp_chat al importar este módulo (lo hace controlador_chat.py, que sigue siendo el punto de entrada)."""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, servicio, autenticación…)

# =============================================================================
# REACCIONES
# =============================================================================

@bp_chat.route('/messages/<int:mensaje_id>/reactions', methods=['GET'])
@requiere_autenticacion
def obtener_reacciones(mensaje_id: int):
    """
    Obtiene las reacciones de un mensaje.

    Response:
        {
            "success": true,
            "reactions": [
                {"emoji": "😀", "count": 2, "user_ids": [1, 2]}
            ]
        }
    """
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.obtener_reacciones_mensaje(mensaje_id)

        if resultado.exito:
            return jsonify({
                'success': True,
                'exito': True,
                'reactions': resultado.datos.get('reacciones', [])
            }), 200
        else:
            return jsonify({
                'success': False,
                'exito': False,
                'reactions': [],
                'mensaje': resultado.mensaje
            }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'exito': False,
            'reactions': [],
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/messages/<int:mensaje_id>/reactions', methods=['POST'])
@requiere_autenticacion
def agregar_reaccion(mensaje_id: int):
    """
    Agrega una reaccion a un mensaje.

    Request:
        {
            "emoji": "..."
        }

    Response:
        {
            "exito": true,
            "mensaje": "Reaccion agregada"
        }
    """
    try:
        datos = request.get_json()
        if datos and 'emoji' in datos:
            from interfaces.emoji_reaccion import normalizar_emoji
            datos['emoji'] = normalizar_emoji(datos['emoji'])   # [A-1] solo algo que parezca un emoji
            if datos['emoji'] is None:
                return jsonify({'exito': False, 'success': False, 'mensaje': 'emoji no válido'}), 400
        if not datos or 'emoji' not in datos:
            return jsonify({
                'exito': False,
                'mensaje': 'emoji es requerido'
            }), 400

        servicio = obtener_servicio_chat()
        usuario_id = obtener_usuario_id()
        resultado = servicio.agregar_reaccion(
            mensaje_id=mensaje_id,
            usuario_id=usuario_id,
            emoji=datos['emoji']
        )

        # Si la reaccion se agrego exitosamente, emitir via WebSocket
        if resultado.exito:
            # Obtener el conversacion_id del mensaje
            mensaje = servicio._repo_mensaje.buscar_por_id(mensaje_id)
            if mensaje and mensaje.conversacion_id:
                from datetime import datetime
                emitir_a_conversacion(
                    mensaje.conversacion_id,
                    'reaction_added',
                    {
                        'message_id': mensaje_id,
                        'user_id': usuario_id,
                        'emoji': datos['emoji'],
                        'timestamp': datetime.now().isoformat()
                    }
                )

        status = 200 if resultado.exito else 400
        return jsonify({
            'exito': resultado.exito,
            'success': resultado.exito,  # Alias para compatibilidad con frontend
            'mensaje': resultado.mensaje,
            'reaction': {'emoji': datos['emoji']} if resultado.exito else None
        }), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'success': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/messages/<int:mensaje_id>/reactions', methods=['DELETE'])
@requiere_autenticacion
def eliminar_reaccion(mensaje_id: int):
    """
    Elimina la reaccion del usuario a un mensaje.

    Response:
        {
            "exito": true,
            "mensaje": "Reaccion eliminada"
        }
    """
    try:
        servicio = obtener_servicio_chat()
        usuario_id = obtener_usuario_id()

        # Obtener el conversacion_id ANTES de eliminar para poder emitir el evento
        mensaje = servicio._repo_mensaje.buscar_por_id(mensaje_id)
        conversacion_id = mensaje.conversacion_id if mensaje else None

        resultado = servicio.eliminar_reaccion(
            mensaje_id=mensaje_id,
            usuario_id=usuario_id
        )

        # Si la reaccion se elimino exitosamente, emitir via WebSocket
        if resultado.exito and conversacion_id:
            from datetime import datetime
            emitir_a_conversacion(
                conversacion_id,
                'reaction_removed',
                {
                    'message_id': mensaje_id,
                    'user_id': usuario_id,
                    'timestamp': datetime.now().isoformat()
                }
            )

        return jsonify({
            'exito': resultado.exito,
            'success': resultado.exito,  # Alias para compatibilidad con frontend
            'mensaje': resultado.mensaje
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'success': False,
            'mensaje': 'Error interno del servidor'
        }), 500

