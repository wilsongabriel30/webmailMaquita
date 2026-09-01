# -*- coding: utf-8 -*-
"""
Estado de entrega de mensajes (✓ enviado / ✓✓ entregado / ✓✓ azul leído).
==========================================================================
- `registrar_entrega_al_listar`: cuando un usuario carga los mensajes de una
  conversación, todo lo que no es suyo queda marcado como ENTREGADO a él
  (chat_message_status.is_delivered). Devuelve los ids recién entregados para
  avisar al remitente en tiempo real.
- `anotar_entregados`: agrega `delivered_at`/`delivered_count` a los mensajes
  propios del listado cuando TODOS los demás participantes activos ya los tienen.
"""
from datetime import datetime

from sqlalchemy import text


def registrar_entrega_al_listar(db_session, conversacion_id, usuario_id, ids_mensajes):
    if not ids_mensajes:
        return []
    try:
        filas = db_session.execute(text("""
            SELECT m.id FROM chat_messages m
            WHERE m.id = ANY(:ids) AND m.conversation_id = :conv AND m.sender_id <> :uid
              AND NOT EXISTS (SELECT 1 FROM chat_message_status s
                              WHERE s.message_id = m.id AND s.user_id = :uid AND s.is_delivered = TRUE)
        """), {'ids': list(ids_mensajes), 'conv': conversacion_id, 'uid': usuario_id}).fetchall()
        pendientes = [f[0] for f in filas]
        if not pendientes:
            return []
        db_session.execute(text("""
            UPDATE chat_message_status SET is_delivered = TRUE, delivered_at = COALESCE(delivered_at, :ahora)
            WHERE message_id = ANY(:ids) AND user_id = :uid
        """), {'ids': pendientes, 'uid': usuario_id, 'ahora': datetime.now()})
        db_session.execute(text("""
            INSERT INTO chat_message_status (message_id, user_id, is_delivered, delivered_at, is_read)
            SELECT m.id, :uid, TRUE, :ahora, FALSE FROM chat_messages m
            WHERE m.id = ANY(:ids)
              AND NOT EXISTS (SELECT 1 FROM chat_message_status s WHERE s.message_id = m.id AND s.user_id = :uid)
        """), {'ids': pendientes, 'uid': usuario_id, 'ahora': datetime.now()})
        db_session.commit()
        return pendientes
    except Exception:
        try:
            db_session.rollback()
        except Exception:
            pass
        return []


def anotar_entregados(mensajes, db_session, conversacion_id, usuario_id):
    propios = [m['id'] for m in mensajes if m.get('is_own_message') and m.get('id')]
    if not propios:
        return mensajes
    try:
        otros = db_session.execute(text("""
            SELECT COUNT(*) FROM chat_participants
            WHERE conversation_id = :conv AND user_id <> :uid AND is_active = TRUE
        """), {'conv': conversacion_id, 'uid': usuario_id}).scalar() or 0
        filas = db_session.execute(text("""
            SELECT message_id, COUNT(DISTINCT user_id) FROM chat_message_status
            WHERE message_id = ANY(:ids) AND user_id <> :uid AND is_delivered = TRUE
            GROUP BY message_id
        """), {'ids': propios, 'uid': usuario_id}).fetchall()
        entregados = {f[0]: f[1] for f in filas}
        for m in mensajes:
            if m.get('is_own_message'):
                n = entregados.get(m['id'], 0)
                m['delivered_count'] = n
                m['delivered_at'] = bool(otros and n >= otros)
    except Exception:
        pass
    return mensajes
