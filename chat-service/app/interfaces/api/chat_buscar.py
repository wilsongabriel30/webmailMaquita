# -*- coding: utf-8 -*-
"""Búsqueda de mensajes.
Extraído de controlador_chat.py (líneas 3390-3456) el 28/08/2026 sin cambios en las rutas. Las rutas se registran en
bp_chat al importar este módulo (lo hace controlador_chat.py, que sigue siendo el punto de entrada)."""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, servicio, autenticación…)

# =============================================================================
# BUSQUEDA DE MENSAJES (dentro de una conversacion o en TODAS) — rapida por SQL
# =============================================================================

@bp_chat.route("/buscar-mensajes", methods=["GET"])
@requiere_autenticacion
def buscar_mensajes():
    """Busca mensajes por contenido. Query: q (texto), conversation_id (opcional).
    Sin conversation_id busca en TODAS las conversaciones del usuario."""
    from sqlalchemy import text as _t
    usuario_id = obtener_usuario_id()
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"exito": True, "resultados": []}), 200
    try:
        conv_id = int(request.args.get("conversation_id")) if request.args.get("conversation_id") else None
    except (TypeError, ValueError):
        conv_id = None

    ses = g.get("db_session_chat")
    if not ses:
        ses = obtener_gestor().session(); g.db_session_chat = ses

    sql = (
        "SELECT m.id, m.conversation_id, m.content, m.created_at, m.message_type, "
        "  u.full_name AS remitente, c.conversation_type, c.name AS conv_name, "
        "  p.cleared_at "
        "FROM chat_messages m "
        "JOIN chat_participants p ON p.conversation_id = m.conversation_id AND p.user_id = :uid AND p.is_active = TRUE "
        "JOIN chat_conversations c ON c.id = m.conversation_id "
        "LEFT JOIN usuarios u ON u.id = m.sender_id "
        "WHERE m.is_deleted = FALSE AND m.content ILIKE :q "
    )
    params = {"uid": usuario_id, "q": "%" + q + "%"}
    if conv_id:
        sql += "AND m.conversation_id = :cid "
        params["cid"] = conv_id
    sql += "ORDER BY m.created_at DESC LIMIT 60"

    filas = ses.execute(_t(sql), params).fetchall()
    # Para chats directos, mostrar el nombre del OTRO participante como titulo
    res = []
    for f in filas:
        cleared = f[8]
        creado = f[3]
        if cleared and creado and creado <= cleared:
            continue  # respeta "vaciar"
        titulo = f[7]
        if (f[6] or "") == "direct":
            otro = ses.execute(_t(
                "SELECT u.full_name FROM chat_participants p JOIN usuarios u ON u.id = p.user_id "
                "WHERE p.conversation_id = :c AND p.user_id <> :u LIMIT 1"
            ), {"c": f[1], "u": usuario_id}).fetchone()
            if otro and otro[0]:
                titulo = otro[0]
        res.append({
            "id": f[0],
            "conversation_id": f[1],
            "contenido": f[2],
            "fecha": creado.isoformat() if creado else None,
            "tipo": f[4],
            "remitente": f[5] or "Sistema",
            "conversation_type": f[6],
            "titulo": titulo or "Conversación",
        })
    return jsonify({"exito": True, "resultados": res, "total": len(res)}), 200
