# -*- coding: utf-8 -*-
"""Mensajes: enviar un GIF (url_gif). Extraído de chat_mensajes_enviar.py (líneas 175-224) el 28/08/2026 sin cambios
de lógica: el cuerpo del `if tipo_mensaje == 'gif'` pasó a enviar_gif(), que devuelve (respuesta, código)."""
from interfaces.api.chat_base import *  # noqa: F401,F403


def enviar_gif(conversacion_id, contenido, gif_url):
    servicio = obtener_servicio_chat()
    usuario_id = obtener_usuario_id()
    resultado = servicio.enviar_gif(
        conversacion_id=conversacion_id,
        remitente_id=usuario_id,
        url_gif=gif_url,
        contenido=contenido or 'GIF'
    )

    if resultado.exito and resultado.datos:
        mensaje_data = resultado.datos.get('mensaje', {})
        mensaje_data['remitente'] = {
            'id': usuario_id,
            'nombre': session.get('usuario_nombre', 'Usuario')
        }
        print(f"[DEBUG-GIF] Enviando GIF via WebSocket:")
        print(f"[DEBUG-GIF]   tipo: {mensaje_data.get('tipo')}")
        print(f"[DEBUG-GIF]   gif_url: {mensaje_data.get('gif_url')}")
        print(f"[DEBUG-GIF]   remitente_id: {mensaje_data.get('remitente_id')}")
        print(f"[DEBUG-GIF]   conversacion_id: {conversacion_id}")
        emitir_mensaje_nuevo(conversacion_id, mensaje_data)

    status = 200 if resultado.exito else 400

    # Respuesta compatible con frontend
    response_data = {
        'exito': resultado.exito,
        'success': resultado.exito,
        'mensaje': resultado.mensaje
    }

    if resultado.datos and resultado.datos.get('mensaje'):
        msg = resultado.datos['mensaje']
        response_data['message'] = {
            'id': msg.get('id'),
            'content': msg.get('contenido'),
            'message_type': 'gif',
            'sender_id': usuario_id,
            'created_at': msg.get('creado_en'),
            'is_own_message': True,
            'media': [{
                'file_path': gif_url,
                'media_type': 'gif'
            }]
        }
        response_data['datos'] = resultado.datos

    return jsonify(response_data), status
