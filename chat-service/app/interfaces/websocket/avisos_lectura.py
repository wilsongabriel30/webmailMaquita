# -*- coding: utf-8 -*-
"""T-45 punto 10 - Aviso de lectura al room personal del remitente (01/09/2026).

El camino HTTP (`POST /conversations/<id>/read`) ya avisaba a `user_<id>` de cada
participante, pero el camino WebSocket (`mark_read`) solo emitia a
`conversation_<id>`. Resultado: si quien envio el mensaje no tenia esa
conversacion abierta, su visto no se encendia hasta recargar. Aqui se emite a los
dos sitios, para que el estado cambie en el acto en cualquier pantalla.
"""
import logging

logger = logging.getLogger(__name__)


def avisar_lectura(socketio, conversacion_id, lector_id, hasta_mensaje_id=None):
    """Avisa a los demas participantes de la conversacion que `lector_id` leyo.

    Se emite a `user_<id>` de cada participante distinto del lector (nunca al
    propio lector: marcaria como leidos sus propios mensajes enviados).
    Devuelve a cuantas personas se aviso; nunca lanza excepcion.
    """
    if not socketio or not conversacion_id or not lector_id:
        return 0
    try:
        from sqlalchemy import text
        from infraestructura.base_datos.base import obtener_gestor

        sesion = obtener_gestor().session()
        try:
            otros = sesion.execute(text(
                "SELECT user_id FROM chat_participants "
                "WHERE conversation_id = :c AND user_id <> :u AND is_active = TRUE"
            ), {'c': conversacion_id, 'u': lector_id}).fetchall()
        finally:
            sesion.close()

        datos = {
            'conversation_id': conversacion_id,
            'hasta_mensaje_id': hasta_mensaje_id,
            'until_message_id': hasta_mensaje_id,
            'reader_id': lector_id,
            'read_by': lector_id,
        }
        for fila in otros:
            socketio.emit('messages_read', datos, room=f"user_{fila[0]}")
        return len(otros)
    except Exception as e:
        logger.warning(f"[lectura] no se pudo avisar de la lectura: {e}")
        return 0
