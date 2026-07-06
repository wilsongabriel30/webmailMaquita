# -*- coding: utf-8 -*-
"""
Servicio de Chat Maquita — arranque standalone (Flask + Socket.IO).
====================================================================
Servicio de chat INDEPENDIENTE (Fase A). El controlador del chat ya está
desacoplado de las capas globales del sistema de origen (dominio/infraestructura
eran bridges legacy → reapuntados a modulos.chat.*).

Auth: JWT propio (secreto compartido con el cliente/correo; en producción Keycloak).
El before_request traduce el JWT (sub=correo) a la sesión que el controlador espera
(session['usuario_id']), resolviendo el correo contra la BD de usuarios.

Tiempo real: Socket.IO con Redis como message_queue (escalable a varios workers).
"""
import os
import sys

_BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_BASE, "app"))
sys.path.insert(0, os.path.join(_BASE, "shims"))

from flask import Flask, request, jsonify, session

_JWT_SECRET = os.getenv("CHAT_JWT_SECRET", "")
_RUTAS_PROTEGIDAS = ("/api/chat", "/chat", "/socket.io")


def _resolver_usuario():
    """Valida el JWT del cliente y devuelve (usuario_id, correo) o (None, None).
    Mapea el correo del token al id de usuario en la BD (piloto). En producción
    el emisor será Keycloak con el id ya en el token."""
    if not _JWT_SECRET:
        return None, None
    import jwt
    tok = request.cookies.get("access_token") or ""
    auth = request.headers.get("Authorization", "")
    if not tok and auth.startswith("Bearer "):
        tok = auth[7:]
    if not tok:
        return None, None
    try:
        datos = jwt.decode(tok, _JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None, None
    if datos.get("type") not in (None, "access"):
        return None, None
    correo = (datos.get("sub") or "").strip().lower()
    if not correo:
        return None, None
    # correo -> usuario_id (BD). Cacheado por proceso.
    uid = _uid_por_correo(correo)
    return uid, correo


_cache_uid = {}


def _uid_por_correo(correo):
    if correo in _cache_uid:
        return _cache_uid[correo]
    try:
        import psycopg2
        dsn = os.getenv("USERS_DB_URL") or os.getenv("DATABASE_URL")
        con = psycopg2.connect(dsn)
        cur = con.cursor()
        cur.execute("SELECT id FROM usuarios WHERE lower(email)=%s AND active=true LIMIT 1", (correo,))
        row = cur.fetchone()
        con.close()
        uid = int(row[0]) if row else None
    except Exception:
        uid = None
    _cache_uid[correo] = uid
    return uid


def crear_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("CHAT_SESSION_KEY", os.urandom(24).hex())

    @app.get("/healthz")
    def healthz():
        return jsonify({"success": True, "servicio": "chat-maquita"})

    # Montar el chat (62 endpoints). El controlador ya carga desacoplado.
    try:
        from interfaces.api.controlador_chat import bp_chat
        app.register_blueprint(bp_chat)
        app.config["CHAT_MONTADO"] = True
    except Exception as e:
        app.config["CHAT_MONTADO"] = False
        app.config["CHAT_ERROR"] = str(e)

    @app.before_request
    def _auth():
        if request.path.startswith(_RUTAS_PROTEGIDAS):
            if session.get("usuario_id"):
                return None
            uid, correo = _resolver_usuario()
            if not uid:
                return jsonify({"success": False, "error": "No autenticado"}), 401
            session["usuario_id"] = uid
            session["usuario_correo"] = correo
        return None

    return app


application = crear_app()

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=int(os.getenv("CHAT_PORT", "8790")))
