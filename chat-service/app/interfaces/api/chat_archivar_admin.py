# -*- coding: utf-8 -*-
"""Archivar/vaciar/eliminar conversación y panel admin.
Extraído de controlador_chat.py (líneas 3254-3389) el 28/08/2026 sin cambios en las rutas. Las rutas se registran en
bp_chat al importar este módulo (lo hace controlador_chat.py, que sigue siendo el punto de entrada)."""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, servicio, autenticación…)

# =============================================================================
# ACCIONES DE CONVERSACION (archivar / vaciar / eliminar) — SOFT, sin perder datos
# El historial completo queda en BD y es visible desde el panel admin del chat.
# =============================================================================

def _es_master(usuario_id):
    try:
        from sqlalchemy import text as _t
        ses = g.get("db_session_chat")
        if not ses:
            ses = obtener_gestor().session(); g.db_session_chat = ses
        r = ses.execute(_t("SELECT role FROM usuarios WHERE id = :id"), {"id": usuario_id}).fetchone()
        return bool(r and str(r[0]) in ("master", "master_admin"))
    except Exception:
        return False


@bp_chat.route("/conversations/<int:conversacion_id>/archivar", methods=["POST"])
@requiere_autenticacion
def archivar_conversacion(conversacion_id):
    """Archiva/desarchiva la conversacion SOLO para el usuario actual (reversible)."""
    from sqlalchemy import text as _t
    usuario_id = obtener_usuario_id()
    datos = request.get_json(silent=True) or {}
    archivar = datos.get("archivar", True)
    ses = g.get("db_session_chat")
    if not ses:
        ses = obtener_gestor().session(); g.db_session_chat = ses
    ses.execute(_t(
        "UPDATE chat_participants SET is_archived = :a, archived_at = CASE WHEN :a THEN NOW() ELSE NULL END "
        "WHERE conversation_id = :c AND user_id = :u"
    ), {"a": bool(archivar), "c": conversacion_id, "u": usuario_id})
    ses.commit()
    return jsonify({"exito": True, "success": True, "archivada": bool(archivar)}), 200


@bp_chat.route("/conversations/<int:conversacion_id>/vaciar", methods=["POST"])
@requiere_autenticacion
def vaciar_conversacion(conversacion_id):
    """Vacia la conversacion para el usuario (los mensajes previos dejan de mostrarse,
    pero NO se borran de la BD; quedan en el historial admin)."""
    from sqlalchemy import text as _t
    usuario_id = obtener_usuario_id()
    ses = g.get("db_session_chat")
    if not ses:
        ses = obtener_gestor().session(); g.db_session_chat = ses
    ses.execute(_t(
        "UPDATE chat_participants SET cleared_at = NOW() WHERE conversation_id = :c AND user_id = :u"
    ), {"c": conversacion_id, "u": usuario_id})
    ses.commit()
    return jsonify({"exito": True, "success": True}), 200


@bp_chat.route("/conversations/<int:conversacion_id>/eliminar", methods=["POST"])
@requiere_autenticacion
def eliminar_conversacion(conversacion_id):
    """Elimina la conversacion de la lista del usuario (borrado LOGICO: is_active=false).
    Los datos siguen en BD y son recuperables desde el panel admin."""
    from sqlalchemy import text as _t
    usuario_id = obtener_usuario_id()
    ses = g.get("db_session_chat")
    if not ses:
        ses = obtener_gestor().session(); g.db_session_chat = ses
    ses.execute(_t(
        "UPDATE chat_participants SET is_active = FALSE, left_at = NOW() "
        "WHERE conversation_id = :c AND user_id = :u"
    ), {"c": conversacion_id, "u": usuario_id})
    ses.commit()
    return jsonify({"exito": True, "success": True}), 200


# ---------- PANEL ADMIN: historial de conversaciones (recuperar/revisar) ----------

@bp_chat.route("/admin/conversaciones", methods=["GET"])
@requiere_autenticacion
def admin_listar_conversaciones():
    """Lista TODAS las conversaciones (incluidas archivadas/eliminadas) para master.
    Permite revisar/recuperar. Query: q (filtro por participante)."""
    from sqlalchemy import text as _t
    usuario_id = obtener_usuario_id()
    if not _es_master(usuario_id):
        return jsonify({"exito": False, "error": "Solo administradores"}), 403
    q = (request.args.get("q") or "").strip()
    ses = g.get("db_session_chat")
    if not ses:
        ses = obtener_gestor().session(); g.db_session_chat = ses
    base = (
        "SELECT c.id, c.conversation_type, c.name, c.created_at, "
        "  (SELECT count(*) FROM chat_messages m WHERE m.conversation_id = c.id) AS n_msgs, "
        "  (SELECT max(m.created_at) FROM chat_messages m WHERE m.conversation_id = c.id) AS ultimo, "
        "  (SELECT string_agg(DISTINCT u.full_name, \' , \') FROM chat_participants p "
        "      JOIN usuarios u ON u.id = p.user_id WHERE p.conversation_id = c.id) AS participantes "
        "FROM chat_conversations c "
    )
    params = {}
    if q:
        base += ("WHERE c.id IN (SELECT p.conversation_id FROM chat_participants p "
                 "JOIN usuarios u ON u.id = p.user_id WHERE u.full_name ILIKE :q) ")
        params["q"] = "%" + q + "%"
    base += "ORDER BY ultimo DESC NULLS LAST LIMIT 200"
    filas = ses.execute(_t(base), params).fetchall()
    convs = [{
        "id": f[0], "tipo": f[1], "nombre": f[2],
        "creado_en": f[3].isoformat() if f[3] else None,
        "n_mensajes": f[4] or 0,
        "ultimo": f[5].isoformat() if f[5] else None,
        "participantes": f[6] or "",
    } for f in filas]
    return jsonify({"exito": True, "conversaciones": convs}), 200


@bp_chat.route("/admin/conversaciones/<int:conversacion_id>/mensajes", methods=["GET"])
@requiere_autenticacion
def admin_mensajes_conversacion(conversacion_id):
    """Todos los mensajes de una conversacion (para revision/recuperacion) — master."""
    from sqlalchemy import text as _t
    usuario_id = obtener_usuario_id()
    if not _es_master(usuario_id):
        return jsonify({"exito": False, "error": "Solo administradores"}), 403
    ses = g.get("db_session_chat")
    if not ses:
        ses = obtener_gestor().session(); g.db_session_chat = ses
    filas = ses.execute(_t(
        "SELECT m.id, m.sender_id, u.full_name, m.content, m.message_type, m.created_at, m.is_deleted "
        "FROM chat_messages m LEFT JOIN usuarios u ON u.id = m.sender_id "
        "WHERE m.conversation_id = :c ORDER BY m.created_at ASC LIMIT 2000"
    ), {"c": conversacion_id}).fetchall()
    msgs = [{
        "id": f[0], "remitente_id": f[1], "remitente": f[2] or "Sistema",
        "contenido": f[3], "tipo": f[4],
        "fecha": f[5].isoformat() if f[5] else None,
        "eliminado": bool(f[6]),
    } for f in filas]
    return jsonify({"exito": True, "mensajes": msgs}), 200

