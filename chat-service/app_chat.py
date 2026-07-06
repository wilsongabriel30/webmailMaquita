# -*- coding: utf-8 -*-
"""
Servicio de Chat Maquita — arranque standalone (Flask + Socket.IO).
====================================================================
ANDAMIAJE (Fase A). Monta el chat como servicio independiente, sin FARO:
- Auth por JWT propio (secreto compartido con el cliente; luego Keycloak).
- Socket.IO para tiempo real (Redis como message_queue → escalable a varios workers).
- El blueprint del chat vive en app/interfaces/api/controlador_chat.py.

PENDIENTE de la siguiente iteración (documentado en el README):
- Resolver los imports del sistema de origen con los shims/ (Base SQLAlchemy, websocket).
- Migraciones de la BD del chat.
- Prueba end-to-end (mensajes, presencia, video LiveKit).
No arranca en produccion todavia; el chat sigue sirviendose desde su instancia actual.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "shims"))

from flask import Flask, request, jsonify

_SECRET = os.getenv("CHAT_JWT_SECRET", "")


def _usuario_de_jwt():
    """Valida el JWT del cliente (cookie access_token o Authorization Bearer).
    Devuelve el identificador del usuario o None. Auth del piloto; en produccion
    el emisor sera Keycloak (mismo patron, otra clave/validacion)."""
    if not _SECRET:
        return None
    import jwt
    tok = request.cookies.get("access_token") or ""
    auth = request.headers.get("Authorization", "")
    if not tok and auth.startswith("Bearer "):
        tok = auth[7:]
    if not tok:
        return None
    try:
        datos = jwt.decode(tok, _SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return (datos.get("sub") or "").strip().lower() or None


def crear_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("CHAT_SESSION_KEY", os.urandom(24).hex())

    @app.get("/healthz")
    def healthz():
        return jsonify({"success": True, "servicio": "chat-maquita"})

    # NOTA (Fase A pendiente): montar aqui el blueprint del chat
    #   from interfaces.api.controlador_chat import bp_chat
    #   app.register_blueprint(bp_chat)
    # tras resolver los shims (Base, websocket) y el before_request de auth que
    # traduzca el JWT (_usuario_de_jwt) a la sesion que el controlador espera.

    @app.before_request
    def _auth():
        if request.path.startswith("/api/chat"):
            if not _usuario_de_jwt():
                return jsonify({"success": False, "error": "No autenticado"}), 401
        return None

    return app


application = crear_app()

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=int(os.getenv("CHAT_PORT", "8790")))
