# -*- coding: utf-8 -*-
"""Mensajes: enviar (POST) — texto; adjuntos y GIF viven en chat_mensajes_enviar_archivos.py / _gif.py (28/08/2026).
Extraído de chat_mensajes.py (líneas 282-570) el 28/08/2026 sin cambios en las rutas; se registran en bp_chat al importarlo
(lo hace chat_mensajes.py, que sigue siendo el punto de entrada de mensajes)."""
from interfaces.api.chat_base import *  # noqa: F401,F403
from interfaces.api.chat_mensajes_enviar_archivos import enviar_con_archivos  # noqa: E402
from interfaces.api.chat_mensajes_enviar_gif import enviar_gif  # noqa: E402


@bp_chat.route('/conversations/<int:conversacion_id>/messages', methods=['POST'])
@bp_chat.route('/conversaciones/<int:conversacion_id>/mensajes', methods=['POST'])  # Alias español
@requiere_autenticacion
def enviar_mensaje(conversacion_id: int):
    """
    Envia un mensaje a una conversacion.

    Request:
        {
            "contenido": "texto del mensaje",
            "tipo": "text" (opcional),
            "respuesta_a": int (opcional)
        }

    Response:
        {
            "exito": true,
            "mensaje": {...}
        }
    """
    try:
        # Soportar tanto JSON como multipart/form-data (para archivos)
        if request.content_type and 'multipart/form-data' in request.content_type:
            datos = {
                'contenido': request.form.get('content', '') or request.form.get('contenido', ''),
                'tipo': request.form.get('message_type', 'document') or request.form.get('tipo', 'document'),
            }
            archivos = request.files.getlist('files')
        else:
            datos = request.get_json()
            archivos = []

        if not datos:
            return jsonify({
                'exito': False,
                'mensaje': 'Datos no proporcionados'
            }), 400

        # Si hay archivos adjuntos: chat_mensajes_enviar_archivos.py (partido el 28/08/2026)
        if archivos:
            return enviar_con_archivos(conversacion_id, datos, archivos)

        # Aceptar 'contenido' o 'content' para compatibilidad con frontend
        contenido = (datos.get('contenido') or datos.get('content', '')).strip()
        tipo_mensaje = datos.get('tipo') or datos.get('message_type', 'text')
        gif_url = datos.get('gif_url') or datos.get('url')

        # Si es un GIF: chat_mensajes_enviar_gif.py (partido el 28/08/2026)
        if tipo_mensaje == 'gif' and gif_url:
            return enviar_gif(conversacion_id, contenido, gif_url)

        if not contenido:
            return jsonify({
                'exito': False,
                'success': False,
                'mensaje': 'El contenido es requerido'
            }), 400

        servicio = obtener_servicio_chat()
        usuario_id = obtener_usuario_id()
        resultado = servicio.enviar_mensaje(
            conversacion_id=conversacion_id,
            remitente_id=usuario_id,
            contenido=contenido,
            tipo=tipo_mensaje,
            respuesta_a_id=datos.get('respuesta_a') or datos.get('reply_to_id')
        )

        # T-49: la hora en que se escribio (puede venir de la cola del equipo, si se
        # escribio sin internet). Se guarda aparte de la hora de llegada.
        from interfaces.api import hora_original
        escrito_en = hora_original.leer(datos)
        if escrito_en and resultado.exito and resultado.datos:
            _msg = resultado.datos.get('mensaje') or {}
            if hora_original.guardar(g.get('db_session_chat') or obtener_gestor().session(),
                                     _msg.get('id'), escrito_en):
                _msg['escrito_en'] = hora_original.para_mostrar(escrito_en)

        # Emitir via WebSocket si fue exitoso
        if resultado.exito and resultado.datos:
            mensaje_data = resultado.datos.get('mensaje', {})
            mensaje_data['remitente'] = {
                'id': usuario_id,
                'nombre': session.get('usuario_nombre', 'Usuario')
            }
            emitir_mensaje_nuevo(conversacion_id, mensaje_data)

        status = 200 if resultado.exito else 400

        # Respuesta compatible con frontend (success + message)
        response_data = {
            'exito': resultado.exito,
            'success': resultado.exito,
            'mensaje': resultado.mensaje
        }

        # Incluir mensaje enviado en formato compatible
        if resultado.datos and resultado.datos.get('mensaje'):
            msg = resultado.datos['mensaje']
            response_data['message'] = {
                'id': msg.get('id'),
                'content': msg.get('contenido'),
                'message_type': msg.get('tipo', 'text'),
                'sender_id': usuario_id,
                'created_at': msg.get('creado_en'),
                # T-49: la hora en que se escribio, si fue distinta de la de llegada
                'escrito_en': msg.get('escrito_en'),
                'is_own_message': True
            }
            response_data['datos'] = resultado.datos

        return jsonify(response_data), status

    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error enviando mensaje: {e}")
        traceback.print_exc()

        # Intentar hacer rollback manual si hay sesion
        db_session = g.get('db_session_chat')
        if db_session:
            try:
                db_session.rollback()
            except:
                pass

        return jsonify({
            'exito': False,
            'success': False,
            'mensaje': f'Error interno del servidor: {str(e)}'
        }), 500
