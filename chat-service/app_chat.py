# -*- coding: utf-8 -*-
"""
Servicio de Chat Maquita — arranque standalone (Flask + Socket.IO).
====================================================================
Servicio de chat INDEPENDIENTE. El controlador del chat está desacoplado de las
capas globales del sistema de origen (dominio/infraestructura eran bridges legacy
→ reapuntados a modulos.chat.*).

Auth: JWT propio (secreto compartido con el cliente/correo; en producción Keycloak).
El before_request traduce el JWT (sub=correo) a la sesión que el controlador espera
(session['usuario_id']), resolviendo el correo contra la BD de usuarios.

Tiempo real: Socket.IO (eventlet) con Redis como message_queue → escalable a varios
workers. La BD del chat se inicializa al arrancar.
"""
# eventlet debe parchear ANTES de importar cualquier librería de red/BD.
import eventlet  # noqa
eventlet.monkey_patch()

import os
import sys
from urllib.parse import urlparse

_BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_BASE, "app"))
sys.path.insert(0, os.path.join(_BASE, "shims"))

from flask import Flask, request, jsonify, session, render_template

_PLANTILLAS = os.path.join(_BASE, "app", "interfaces", "web", "plantillas")
_ESTATICOS = os.path.join(_BASE, "app", "interfaces", "web", "estaticos")

_JWT_SECRET = os.getenv("CHAT_JWT_SECRET", "")
_REDIS_URL = os.getenv("CHAT_REDIS_URL", "")
_RUTAS_PROTEGIDAS = ("/api/chat", "/chat", "/socket.io")

# [B1] El chat no puede verificar tokens sin su secreto: aborta el arranque si falta
# o tiene valor de ejemplo. Solo nombra la variable, nunca el valor.
def _validar_secreto_chat():
    _v = (_JWT_SECRET or "").strip()
    _PLACEHOLDER = ("change", "example", "placeholder", "tu-secreto", "your-secret", "changeme")
    if not _v or any(p in _v.lower() for p in _PLACEHOLDER):
        raise RuntimeError(
            "Falta CHAT_JWT_SECRET (o tiene un valor de ejemplo) — el chat no puede "
            "verificar tokens. Definelo en el entorno con un valor real."
        )


_validar_secreto_chat()




def _sembrar_redis():
    """Crea el cliente Redis singleton con las credenciales del .env ANTES de que
    los módulos del chat lo instancien con valores por defecto (localhost sin clave)."""
    if not _REDIS_URL:
        return
    try:
        u = urlparse(_REDIS_URL)
        from modulos.chat.infraestructura.cache.cliente_redis import obtener_cliente_redis
        obtener_cliente_redis(
            host=u.hostname or "localhost",
            port=u.port or 6379,
            db=int((u.path or "/0").lstrip("/") or 0),
            password=u.password or None,
        )
    except Exception as e:  # nunca tumbar el arranque por Redis: hay fallback in-memory
        print(f"[chat] aviso: no se pudo sembrar Redis: {e}", file=sys.stderr)


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
    uid = _uid_por_correo(correo)
    return uid, correo


_cache_uid = {}
_cache_nombre = {}


def _uid_por_correo(correo):
    if correo in _cache_uid:
        return _cache_uid[correo]
    try:
        import psycopg2
        dsn = os.getenv("USERS_DB_URL") or os.getenv("DATABASE_URL")
        con = psycopg2.connect(dsn)
        cur = con.cursor()
        cur.execute("SELECT id, COALESCE(NULLIF(TRIM(full_name), ''), username, email) FROM usuarios WHERE lower(email)=%s AND active=true LIMIT 1", (correo,))
        row = cur.fetchone()
        con.close()
        uid = int(row[0]) if row else None
        if row:
            _cache_nombre[uid] = row[1]
    except Exception:
        uid = None
    _cache_uid[correo] = uid
    return uid


def crear_app():
    # BD del chat: inicializar el gestor global antes de montar el controlador.
    from compartido.infraestructura.base_datos import inicializar_base_datos
    inicializar_base_datos(os.environ["DATABASE_URL"])

    _sembrar_redis()

    app = Flask(
        __name__,
        template_folder=_PLANTILLAS,
        static_folder=_ESTATICOS,
        static_url_path="/static",
    )
    app.secret_key = os.getenv("CHAT_SESSION_KEY", os.urandom(24).hex())
    # Cookie de sesión PROPIA: el servicio se consume desde dominios donde ya existe
    # una cookie "session" ajena (FARO). Sin esto se pisarían mutuamente.
    app.config["SESSION_COOKIE_NAME"] = "chat_session"
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = True

    class _UsuarioSesion:
        """Shim para las plantillas: expone .id / .is_authenticated desde la sesión
        (el chat autentica por JWT del correo, no por Flask-Login)."""
        def __init__(self, uid):
            self.id = uid
            self.is_authenticated = uid is not None

    @app.context_processor
    def _inyectar_usuario():
        return {"current_user": _UsuarioSesion(session.get("usuario_id"))}

    @app.get("/healthz")
    def healthz():
        return jsonify({
            "success": True,
            "servicio": "chat-maquita",
            "chat_montado": app.config.get("CHAT_MONTADO", False),
        })

    @app.route("/chat/")
    @app.route("/chat")
    def pagina_chat():
        # La protege el before_request (exige JWT válido → session['usuario_id']).
        return render_template("chat/index.html")

    # Montar el chat (62 endpoints). El controlador ya carga desacoplado.
    try:
        from interfaces.api.controlador_chat import bp_chat
        app.register_blueprint(bp_chat)
        app.config["CHAT_MONTADO"] = True
        # Biblioteca LOCAL de GIF (sin proveedores externos)
        from interfaces.api.controlador_gifs import bp_gifs, asegurar_tabla
        asegurar_tabla()
        app.register_blueprint(bp_gifs)
        # Responder / citar mensajes
        from interfaces.api.citas_respuesta import bp_citas
        app.register_blueprint(bp_citas)
    except Exception as e:
        app.config["CHAT_MONTADO"] = False
        app.config["CHAT_ERROR"] = str(e)
        print(f"[chat] ERROR montando el controlador: {e}", file=sys.stderr)

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
            session["usuario_nombre"] = _cache_nombre.get(uid, correo)
        return None

    return app


application = crear_app()

# Socket.IO (tiempo real). Envuelve la app Flask; gunicorn usa el worker eventlet.
from interfaces.websocket.manejador_websocket import crear_socketio
socketio = crear_socketio(application, redis_url=_REDIS_URL or None)

if __name__ == "__main__":
    socketio.run(application, host="0.0.0.0", port=int(os.getenv("CHAT_PORT", "8790")))
