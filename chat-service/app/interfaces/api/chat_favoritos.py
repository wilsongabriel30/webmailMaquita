# -*- coding: utf-8 -*-
"""T-50 puntos 8 y 9 - Conversaciones favoritas (la seccion «Favoritos» de Teams).

Cada persona fija las conversaciones que usa a diario y suben arriba del todo, en su propia
seccion. Es por usuario: que yo fije un chat no se lo fija a nadie mas.

  POST   /api/chat/favoritos/<conversacion_id>   fijar
  DELETE /api/chat/favoritos/<conversacion_id>   quitar
  GET    /api/chat/favoritos                     los identificadores fijados
"""
from sqlalchemy import text

from interfaces.api.chat_base import *  # noqa: F401,F403

TABLA = """
CREATE TABLE IF NOT EXISTS chat_conversaciones_favoritas (
    usuario_id       INTEGER NOT NULL,
    conversation_id  BIGINT  NOT NULL,
    fijado_en        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (usuario_id, conversation_id)
)
"""


def _sesion():
    ses = g.get('db_session_chat')
    if not ses:
        ses = obtener_gestor().session()
        g.db_session_chat = ses
    return ses


def _asegurar_tabla(ses):
    """Se crea sola la primera vez: evita tener que acordarse de una migracion aparte."""
    ses.execute(text(TABLA))
    ses.commit()


@bp_chat.route('/favoritos', methods=['GET'])
@requiere_autenticacion
def listar_favoritos():
    ses = _sesion()
    _asegurar_tabla(ses)
    filas = ses.execute(text(
        "SELECT conversation_id FROM chat_conversaciones_favoritas "
        "WHERE usuario_id = :u ORDER BY fijado_en"
    ), {'u': obtener_usuario_id()}).fetchall()
    return jsonify({'exito': True, 'success': True,
                    'favoritos': [int(f[0]) for f in filas]}), 200


@bp_chat.route('/favoritos/<int:conversacion_id>', methods=['POST'])
@requiere_autenticacion
def fijar_favorito(conversacion_id: int):
    ses = _sesion()
    _asegurar_tabla(ses)
    usuario_id = obtener_usuario_id()
    # solo se puede fijar una conversacion en la que se participa
    participa = ses.execute(text(
        "SELECT 1 FROM chat_participants WHERE conversation_id = :c AND user_id = :u "
        "AND is_active = TRUE"
    ), {'c': conversacion_id, 'u': usuario_id}).fetchone()
    if not participa:
        return jsonify({'exito': False, 'success': False,
                        'mensaje': 'esa conversación no es tuya'}), 403
    ses.execute(text(
        "INSERT INTO chat_conversaciones_favoritas (usuario_id, conversation_id) "
        "VALUES (:u, :c) ON CONFLICT DO NOTHING"
    ), {'u': usuario_id, 'c': conversacion_id})
    ses.commit()
    return jsonify({'exito': True, 'success': True, 'favorito': True}), 200


@bp_chat.route('/favoritos/<int:conversacion_id>', methods=['DELETE'])
@requiere_autenticacion
def quitar_favorito(conversacion_id: int):
    ses = _sesion()
    _asegurar_tabla(ses)
    ses.execute(text(
        "DELETE FROM chat_conversaciones_favoritas WHERE usuario_id = :u AND conversation_id = :c"
    ), {'u': obtener_usuario_id(), 'c': conversacion_id})
    ses.commit()
    return jsonify({'exito': True, 'success': True, 'favorito': False}), 200


def ids_favoritas(ses, usuario_id):
    """Para que la lista de conversaciones pueda marcar cuales son favoritas."""
    try:
        _asegurar_tabla(ses)
        filas = ses.execute(text(
            "SELECT conversation_id FROM chat_conversaciones_favoritas WHERE usuario_id = :u"
        ), {'u': usuario_id}).fetchall()
        return {int(f[0]) for f in filas}
    except Exception:
        return set()
