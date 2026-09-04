# -*- coding: utf-8 -*-
"""Mensajes: editar, eliminar y limpiar conversación.
Extraído de chat_mensajes.py (líneas 571-758) el 28/08/2026 sin cambios en las rutas; se registran en bp_chat al importarlo
(lo hace chat_mensajes.py, que sigue siendo el punto de entrada de mensajes)."""
from interfaces.api.chat_base import *  # noqa: F401,F403


@bp_chat.route('/messages/<int:mensaje_id>', methods=['PUT'])
@requiere_autenticacion
def editar_mensaje(mensaje_id: int):
    """
    Edita un mensaje existente.

    Request:
        {
            "contenido": "nuevo texto"
        }

    Response:
        {
            "exito": true,
            "mensaje": {...}
        }
    """
    try:
        datos = request.get_json()
        if not datos or 'contenido' not in datos:
            return jsonify({
                'exito': False,
                'mensaje': 'contenido es requerido'
            }), 400

        servicio = obtener_servicio_chat()
        resultado = servicio.editar_mensaje(
            mensaje_id=mensaje_id,
            usuario_id=obtener_usuario_id(),
            nuevo_contenido=datos['contenido']
        )

        # Emitir via WebSocket si fue exitoso
        if resultado.exito and resultado.datos:
            mensaje_data = resultado.datos.get('mensaje', {})
            conversacion_id = mensaje_data.get('conversacion_id')
            nuevo_texto = mensaje_data.get('contenido') or datos.get('contenido') or datos.get('content') or ''
            if conversacion_id:
                emitir_a_conversacion(conversacion_id, 'message_edited', mensaje_data)
                # Si el mensaje editado es el ULTIMO de la conversacion, actualizar la
                # previsualizacion de la bandeja (y avisar para refrescar el listado).
                try:
                    from sqlalchemy import text as _t
                    ses = g.get('db_session_chat')
                    if not ses:
                        ses = obtener_gestor().session(); g.db_session_chat = ses
                    res = ses.execute(_t("""
                        UPDATE chat_conversations c
                        SET last_message_preview = :prev, updated_at = NOW()
                        WHERE c.id = :conv
                          AND :mid = (SELECT id FROM chat_messages
                                      WHERE conversation_id = :conv AND is_deleted = false
                                      ORDER BY created_at DESC, id DESC LIMIT 1)
                    """), {'prev': (nuevo_texto or '')[:100], 'conv': conversacion_id, 'mid': mensaje_id})
                    ses.commit()
                    if res.rowcount:
                        emitir_a_conversacion(conversacion_id, 'conversation_preview', {
                            'conversation_id': conversacion_id,
                            'preview': (nuevo_texto or '')[:100]
                        })
                except Exception:
                    pass

        status = 200 if resultado.exito else 400
        return jsonify({
            'exito': resultado.exito,
            'mensaje': resultado.mensaje,
            'datos': resultado.datos
        }), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/messages/<int:mensaje_id>', methods=['DELETE'])
@requiere_autenticacion
def eliminar_mensaje(mensaje_id: int):
    """
    Elimina un mensaje.

    Query params:
        para_todos: bool (default false)
        conversation_id: int (opcional, para notificacion WebSocket)

    Response:
        {
            "exito": true,
            "mensaje": "Mensaje eliminado"
        }
    """
    try:
        para_todos = (request.args.get('para_todos', 'false').lower() == 'true'
                      or request.args.get('for_everyone', 'false').lower() == 'true')
        conversacion_id = request.args.get('conversation_id', type=int)
        usuario_id = obtener_usuario_id()

        servicio = obtener_servicio_chat()
        resultado = servicio.eliminar_mensaje(
            mensaje_id=mensaje_id,
            usuario_id=usuario_id,
            para_todos=para_todos
        )

        # Emitir via WebSocket si fue exitoso
        if resultado.exito and conversacion_id:
            from datetime import timezone as _tz
            emitir_a_conversacion(conversacion_id, 'message_deleted', {
                'message_id': mensaje_id,
                'deleted_by': usuario_id,
                'for_all': para_todos,
                'timestamp': datetime.now(_tz.utc).isoformat()
            })

        status = 200 if resultado.exito else 400
        return jsonify({
            'exito': resultado.exito,
            'mensaje': resultado.mensaje
        }), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/conversations/<int:conversacion_id>/clear', methods=['DELETE'])
@requiere_autenticacion
def limpiar_conversacion(conversacion_id: int):
    """
    Elimina todos los mensajes de una conversacion (para el usuario actual).
    """
    try:
        usuario_id = obtener_usuario_id()

        from datetime import timezone as _tz
        from sqlalchemy import text as _t

        # Obtener sesion
        db_session = g.get('db_session_chat')
        if not db_session:
            from infraestructura.base_datos.base import obtener_gestor
            gestor = obtener_gestor()
            db_session = gestor.session()
            g.db_session_chat = db_session

        # C-9: quien llama debe ser participante de la conversacion antes de operar
        es_miembro = db_session.execute(_t(
            "SELECT 1 FROM chat_participants WHERE conversation_id = :c AND user_id = :u LIMIT 1"
        ), {"c": conversacion_id, "u": usuario_id}).fetchone()
        if not es_miembro:
            return jsonify({'success': False, 'exito': False,
                            'mensaje': 'No autorizado'}), 403

        from modulos.chat.infraestructura.persistencia.modelos.modelo_mensaje import ModeloMensaje
        mensajes = db_session.query(ModeloMensaje).filter_by(
            conversation_id=conversacion_id,
            is_deleted=False
        ).all()

        count = 0
        ahora = datetime.now(_tz.utc)
        for msg in mensajes:
            msg.is_deleted = True
            msg.deleted_at = ahora
            # Solo borrar para el usuario que lo solicita, no para la otra parte
            msg.deleted_for_everyone = False
            count += 1

        db_session.flush()

        return jsonify({
            'success': True,
            'exito': True,
            'mensaje': f'{count} mensajes eliminados',
            'count': count
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'exito': False,
            'mensaje': 'Error al limpiar conversacion'
        }), 500
