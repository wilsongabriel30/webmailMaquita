# -*- coding: utf-8 -*-
"""T-95 (11/11/2026) - Respuesta rápida desde la notificación de la app de escritorio.

POST /api/chat/conversations/<id>/respuesta-rapida   (alias: /conversaciones/<id>/respuesta-rapida)
Cuerpo: {"texto": "..."}; también acepta "contenido" o "content", formulario o texto plano.
Envía el mensaje igual que el envío normal (chat_mensajes_enviar.py) y responde 200.
"""
from interfaces.api.chat_base import *  # noqa: F401,F403

MAX_CARACTERES = 4000


def _texto_de_la_peticion() -> str:
    datos = request.get_json(silent=True)
    if isinstance(datos, dict):
        valor = datos.get('texto') or datos.get('contenido') or datos.get('content') or ''
    elif request.form:
        valor = request.form.get('texto') or request.form.get('contenido') or request.form.get('content') or ''
    else:
        valor = request.get_data(as_text=True) or ''
    return str(valor).strip()


@bp_chat.route('/conversations/<int:conversacion_id>/respuesta-rapida', methods=['POST'])
@bp_chat.route('/conversaciones/<int:conversacion_id>/respuesta-rapida', methods=['POST'])
@requiere_autenticacion
def respuesta_rapida(conversacion_id: int):
    texto = _texto_de_la_peticion()
    if not texto:
        return jsonify({'exito': False, 'success': False, 'mensaje': 'El texto es requerido'}), 400
    if len(texto) > MAX_CARACTERES:
        return jsonify({'exito': False, 'success': False, 'mensaje': 'El texto es demasiado largo'}), 400
    try:
        usuario_id = obtener_usuario_id()
        resultado = obtener_servicio_chat().enviar_mensaje(
            conversacion_id=conversacion_id,
            remitente_id=usuario_id,
            contenido=texto,
            tipo='text',
            respuesta_a_id=None,
        )
        respuesta = {'exito': resultado.exito, 'success': resultado.exito, 'mensaje': resultado.mensaje}
        if resultado.exito and resultado.datos:
            mensaje = resultado.datos.get('mensaje') or {}
            mensaje['remitente'] = {'id': usuario_id, 'nombre': session.get('usuario_nombre', 'Usuario')}
            emitir_mensaje_nuevo(conversacion_id, mensaje)
            respuesta['message'] = {
                'id': mensaje.get('id'),
                'content': mensaje.get('contenido'),
                'message_type': mensaje.get('tipo', 'text'),
                'sender_id': usuario_id,
                'created_at': mensaje.get('creado_en'),
                'is_own_message': True,
            }
        return jsonify(respuesta), (200 if resultado.exito else 400)
    except Exception as error:  # mismo trato que el envío normal: deshacer y responder 500
        import logging
        logging.getLogger(__name__).error("Error en la respuesta rápida: %s", error)
        sesion_bd = g.get('db_session_chat')
        if sesion_bd:
            try:
                sesion_bd.rollback()
            except Exception:
                pass
        return jsonify({'exito': False, 'success': False, 'mensaje': 'No se pudo enviar el mensaje'}), 500
