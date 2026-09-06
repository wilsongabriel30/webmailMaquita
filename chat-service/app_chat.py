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
# [A-2] Los adjuntos entran aqui: sin esto el before_request no los miraba y
# la carpeta de subidas era publica para quien acertara la ruta.
_RUTAS_PROTEGIDAS = ("/api/chat", "/chat", "/socket.io",
                     "/uploads/chat", "/static/uploads/chat")


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


# --- Entrada desde el correo cuando el chat vive en su propio origen -----------
# Secreto DEDICADO al vale de entrada: ni el del correo (CHAT_JWT_SECRET) ni el de
# la sesión propia (CHAT_SESSION_KEY). Que sean tres evita que comprometer uno
# arrastre a los demás, que es el motivo de separar el origen.
_SSO_SECRET = os.getenv("CHAT_SSO_SECRET", "")
_SSO_AUDIENCIA = "chat-sso"
_SSO_VENTANA_SEG = 120   # margen para el viaje y un reloj algo desfasado


def _consumir_vale(jti: str) -> bool:
    """Marca el vale como usado. Devuelve True solo la PRIMERA vez.

    Falla CERRADO: sin Redis no se puede garantizar el uso único, y un vale
    reutilizable es un pase de sesión que se puede repetir desde un historial.
    """
    if not _REDIS_URL:
        print("[chat] /sso/entrar rechazado: sin CHAT_REDIS_URL no hay uso unico",
              file=sys.stderr)
        return False
    try:
        import redis as _redis
        cli = _redis.Redis.from_url(_REDIS_URL, socket_timeout=2)
        # NX: si ya existía, alguien lo usó antes.
        return bool(cli.set("chat:sso:%s" % jti, "1", ex=_SSO_VENTANA_SEG, nx=True))
    except Exception as e:
        print("[chat] /sso/entrar rechazado: Redis no disponible (%s)" % e, file=sys.stderr)
        return False


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


_PAGINA_401 = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chat Institucional - Raices</title>
<style>body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#f6f7f9;color:#243447;
display:flex;align-items:center;justify-content:center;height:100vh}
.c{max-width:420px;text-align:center;padding:28px;background:#fff;border-radius:14px;
box-shadow:0 6px 24px rgba(0,0,0,.08)}h1{font-size:19px;margin:0 0 10px}p{margin:8px 0;line-height:1.5}
.s{font-size:13px;color:#6b7a8d}.ic{font-size:44px;line-height:1;margin-bottom:6px}a.rein{display:inline-block;margin:12px 8px 0 0;padding:10px 18px;border-radius:8px;border:1px solid #cfd6de;color:#243447;text-decoration:none}a.btn{display:inline-block;margin-top:14px;padding:10px 18px;border-radius:8px;
background:#1f7a4d;color:#fff;text-decoration:none}</style></head><body><div class="c">
<div class="ic">&#128274;</div>
<h1>Tu sesion del chat no esta iniciada</h1>
<p>El chat necesita que inicies sesion en el correo para abrirse.</p>
<p class="s">Motivo: __MOTIVO__</p>
<p class="s" id="r">Reintentando automaticamente&hellip; <span id="n">5</span> s</p>
<a class="rein" href="javascript:location.reload()">Reintentar</a><a class="btn" href="/login?next=/chat/">Iniciar sesion</a></div>
<script>(function(){try{var k="chat401",i=parseInt(sessionStorage.getItem(k)||"0",10);
if(i>=3){var s=document.getElementById("r");if(s)s.textContent="Inicia sesion para continuar.";return;}
sessionStorage.setItem(k,i+1);var n=5;setInterval(function(){n--;var e=document.getElementById("n");
if(e)e.textContent=n;if(n<=0)location.reload();},1000);}catch(e){}})();</script></body></html>"""


def _motivo_no_auth():
    """Devuelve un motivo legible del 401 (para el log y la pagina)."""
    tok = request.cookies.get("access_token") or ""
    auth = request.headers.get("Authorization", "")
    if not tok and auth.startswith("Bearer "):
        tok = auth[7:]
    if not _JWT_SECRET:
        return "el servicio no tiene secreto configurado"
    if not tok:
        return "la ventana no envio la sesion (cookie access_token ausente)"
    try:
        import jwt
        _d = jwt.decode(tok, _JWT_SECRET, algorithms=["HS256"])
        return "la cuenta del token no existe en el directorio (sub=%s)" % (_d.get("sub") or "?")
    except Exception as e:
        nombre = type(e).__name__
        if "Expired" in nombre:
            return "la sesion caduco"
        return "la sesion no es valida (%s)" % nombre


def _respuesta_no_auth():
    """401 que NUNCA deja la ventana en blanco: HTML para paginas, JSON para API."""
    motivo = _motivo_no_auth()
    try:
        print("[chat] 401 %s ip=%s motivo=%s ua=%s" % (
            request.path, request.headers.get("X-Real-IP", request.remote_addr),
            motivo, request.headers.get("User-Agent", "")[:120]), file=sys.stderr)
    except Exception:
        pass
    acepta_html = "text/html" in (request.headers.get("Accept", "") or "")
    es_pagina = request.path.startswith("/chat") and not request.path.startswith("/chat/api")
    if es_pagina and acepta_html:
        return _PAGINA_401.replace("__MOTIVO__", motivo), 401, {"Content-Type": "text/html; charset=utf-8"}
    return jsonify({"success": False, "error": "No autenticado", "motivo": motivo}), 401



def sembrar_desde_token(token):
    """Valida un JWT recibido por la URL (enlaces de notificación) y devuelve
    (usuario_id, correo). Mismo secreto y mismas reglas que la cookie."""
    if not _JWT_SECRET or not token:
        return None, None
    try:
        import jwt
        datos = jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None, None
    if datos.get("type") not in (None, "access"):
        return None, None
    correo = (datos.get("sub") or "").strip().lower()
    if not correo:
        return None, None
    return _uid_por_correo(correo), correo


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


# Dominios institucionales equivalentes: el buzón puede ser usuario@maquita.org y en
# nómina figurar usuario@maquita.com.ec (o viceversa). Misma parte local = misma persona.
_DOMINIOS_EQUIVALENTES = [d.strip().lower() for d in os.getenv(
    "DOMINIOS_EQUIVALENTES", "maquita.org,maquita.com.ec,fundacionmaquita.org").split(",") if d.strip()]


def _uid_por_correo(correo):
    if correo in _cache_uid and _cache_uid[correo] is not None:
        return _cache_uid[correo]          # sólo se cachean aciertos (nunca un "no existe")
    uid = None
    try:
        import psycopg2
        dsn = os.getenv("USERS_DB_URL") or os.getenv("DATABASE_URL")
        con = psycopg2.connect(dsn)
        cur = con.cursor()
        candidatos = [correo]
        local, _, dominio = correo.partition("@")
        if dominio in _DOMINIOS_EQUIVALENTES:
            candidatos += [f"{local}@{d}" for d in _DOMINIOS_EQUIVALENTES if d != dominio]
        for cand in candidatos:
            cur.execute("SELECT id, COALESCE(NULLIF(TRIM(full_name), ''), username, email) FROM usuarios "
                        "WHERE lower(email)=%s AND active=true LIMIT 1", (cand,))
            row = cur.fetchone()
            if row:
                uid = int(row[0])
                _cache_nombre[uid] = row[1]
                if cand != correo:
                    print(f"[chat] alias de correo: {correo} -> {cand} (usuario {uid})", file=sys.stderr)
                break
        con.close()
    except Exception as e:
        print(f"[chat] error resolviendo {correo}: {e}", file=sys.stderr)
        uid = None
    if uid is not None:
        _cache_uid[correo] = uid
    return uid


def crear_app():
    # BD del chat: inicializar el gestor global antes de montar el controlador.
    from compartido.infraestructura.base_datos import inicializar_base_datos
    inicializar_base_datos(os.environ["DATABASE_URL"])

    _sembrar_redis()

    # Los modelos del chat tienen claves foraneas a public.usuarios; sin este import la tabla no esta en
    # los metadatos y SQLAlchemy falla al insertar mensajes con adjuntos (NoReferencedTableError).
    try:
        import modulos.usuarios.infraestructura.persistencia.modelos.modelo_usuario  # noqa: F401
    except Exception as e:
        print(f"[chat] aviso: no se pudo registrar el modelo usuarios: {e}", file=sys.stderr)

    app = Flask(
        __name__,
        template_folder=_PLANTILLAS,
        static_folder=_ESTATICOS,
        static_url_path="/static",
    )
    app.secret_key = os.getenv("CHAT_SESSION_KEY", os.urandom(24).hex())
    # Cookie de sesión PROPIA: el servicio se consume desde dominios donde ya existe
    # una cookie "session" ajena (FARO). Sin esto se pisarían mutuamente.
    # Las plantillas se releen si cambian, para no tener que REINICIAR por cada retoque
    # del HTML. El servicio corre en un solo proceso: cada reinicio corta las conexiones
    # de todo el mundo (1,5 s medidos) y en los equipos sale «el servidor no responde».
    # El coste de esto es comprobar la fecha del archivo en cada uso: nada.
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True

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

    @app.route("/sso/entrar")
    def sso_entrar():
        """Entrada del chat cuando se sirve en SU PROPIO ORIGEN.

        En mail.maquita.org el chat recibía la cookie del correo porque compartían
        origen. En mensajeria.maquita.org esa cookie ya no viaja (es host-only), y
        eso es justamente lo que se buscaba: un XSS en el chat deja de poder leer el
        buzón. A cambio hace falta esta puerta.

        El correo emite un vale de un solo uso, corto y firmado con un secreto
        DEDICADO (CHAT_SSO_SECRET), que no es el del correo ni el de esta sesión.
        Aquí se canjea por la sesión propia del chat (cookie `chat_session`, firmada
        con CHAT_SESSION_KEY, en este origen). El vale no sirve dos veces ni pasado
        el minuto, así que quedar en un historial o en un registro no da acceso.
        """
        vale = request.args.get("t", "")
        destino = request.args.get("r", "") or "/chat/?embed=1"
        # Solo rutas locales: nunca se redirige a un sitio externo con la sesión puesta.
        if not destino.startswith("/") or destino.startswith("//"):
            destino = "/chat/?embed=1"
        if not _SSO_SECRET:
            print("[chat] /sso/entrar sin CHAT_SSO_SECRET configurado", file=sys.stderr)
            return _respuesta_no_auth()
        if not vale:
            return _respuesta_no_auth()
        try:
            import jwt as _jwt
            datos = _jwt.decode(vale, _SSO_SECRET, algorithms=["HS256"],
                                audience=_SSO_AUDIENCIA)
        except Exception as e:
            print("[chat] /sso/entrar vale invalido: %s" % type(e).__name__, file=sys.stderr)
            return _respuesta_no_auth()
        correo = (datos.get("sub") or "").strip().lower()
        jti = (datos.get("jti") or "").strip()
        if not correo or not jti or not _consumir_vale(jti):
            return _respuesta_no_auth()
        uid = _uid_por_correo(correo)
        if not uid:
            return _respuesta_no_auth()
        session["usuario_id"] = uid
        session["usuario_correo"] = correo
        session["usuario_nombre"] = _cache_nombre.get(uid, correo)
        from flask import redirect as _redirect
        return _redirect(destino)

    @app.get("/healthz")
    def healthz():
        return jsonify({
            "success": True,
            "servicio": "chat-maquita",
            "chat_montado": app.config.get("CHAT_MONTADO", False),
        })

    @app.route("/chat/llamada")
    def pagina_llamada():
        """Ventana dedicada de llamada 1:1 (LiveKit). Protegida por el before_request."""
        return render_template("chat/llamada.html")

    @app.route("/chat/llamadas")
    def pagina_llamadas():
        """T-46: discador, historial y favoritos (la sección «Llamadas»)."""
        return render_template("chat/llamadas.html")

    @app.route("/chat/conferencia")
    def pagina_conferencia():
        """Ventana dedicada de llamada grupal (LiveKit)."""
        return render_template("chat/conferencia.html")

    @app.route("/chat/")
    @app.route("/chat")
    def pagina_chat():
        # La protege el before_request (exige JWT válido → session['usuario_id']).
        return render_template("chat/index.html", conv_inicial=request.args.get("conv", ""))

    @app.route("/chat/conversation/<int:conversacion_id>")
    @app.route("/chat/conversacion/<int:conversacion_id>")
    def pagina_chat_conversacion(conversacion_id):
        """Abre el chat directamente en una conversacion (enlaces de notificaciones
        y del cliente Windows). Antes daba 404: la app mostraba «Not Found»."""
        return render_template("chat/index.html", conv_inicial=conversacion_id)

    # Montar el chat (62 endpoints). El controlador ya carga desacoplado.
    try:
        from interfaces.api.controlador_chat import bp_chat
        app.register_blueprint(bp_chat)
        from interfaces.api.archivos_subidos import bp_subidos
        app.register_blueprint(bp_subidos)
        from interfaces.api.metricas_llamadas_api import bp_metricas_llamadas, asegurar_tabla as _asegurar_metricas
        app.register_blueprint(bp_metricas_llamadas)
        from interfaces.api.reuniones_calendario_api import bp_reuniones_vinculo
        app.register_blueprint(bp_reuniones_vinculo)
        from interfaces.api.reuniones_grabaciones_api import bp_reuniones_grab
        app.register_blueprint(bp_reuniones_grab)
        from interfaces.api.adjuntos_dedup import bp_adjuntos_dedup, asegurar_tabla as _asegurar_huellas
        app.register_blueprint(bp_adjuntos_dedup)
        try:
            from interfaces.api.grabaciones_drive import asegurar_tabla as _asegurar_grab
            _asegurar_grab()
        except Exception as _e:
            print("[grabaciones] tabla:", _e)
        try:
            _asegurar_huellas()
        except Exception as _e:
            print("[adjuntos-dedup] tabla:", _e)
        try:
            _asegurar_metricas()
        except Exception as _e:
            print("[metricas-llamadas] tabla:", _e)
        app.config["CHAT_MONTADO"] = True
        # Biblioteca LOCAL de GIF (sin proveedores externos)
        from interfaces.api.controlador_gifs import bp_gifs, asegurar_tabla
        asegurar_tabla()
        app.register_blueprint(bp_gifs)
        # Responder / citar mensajes
        from interfaces.api.citas_respuesta import bp_citas
        app.register_blueprint(bp_citas)
        # Canal único de notificaciones (Teams Maquita, T-03)
        from interfaces.api.notificaciones_api import bp_notificaciones
        app.register_blueprint(bp_notificaciones)
        # Reuniones Meet Maquita (Teams Maquita, T-04)
        from interfaces.api.reuniones_api import bp_reuniones
        app.register_blueprint(bp_reuniones)
        # Calendario del correo (Teams Maquita, T-05): consulta directa a la API del correo
        from interfaces.api.calendario_api import bp_calendario
        app.register_blueprint(bp_calendario)
        # Grupos editables y «Mis notas» (Teams Maquita, T-09 / T-12)
        from interfaces.api.grupos_api import bp_grupos, bp_yo
        app.register_blueprint(bp_grupos)
        app.register_blueprint(bp_yo)
        # Tareas del correo (Teams Maquita, T-15): consulta directa a la API del correo
        from interfaces.api.tareas_api import bp_tareas
        app.register_blueprint(bp_tareas)
        # T-43 (01/09/2026): ficha del compañero al hacer clic en su foto
        from interfaces.api.ficha_persona import bp_ficha
        app.register_blueprint(bp_ficha)
        # Drive ↔ chat (T-18 fase 2): vínculos y eventos de papelera/restauración
        from interfaces.api.llamadas_seccion_api import asegurar_tabla as _tabla_favoritos
        _tabla_favoritos()
        from interfaces.api.drive_eventos_api import bp_drive_eventos, asegurar_tabla as _tabla_drive
        _tabla_drive()
        app.register_blueprint(bp_drive_eventos)
    except Exception as e:
        app.config["CHAT_MONTADO"] = False
        app.config["CHAT_ERROR"] = str(e)
        print(f"[chat] ERROR montando el controlador: {e}", file=sys.stderr)

    @app.before_request
    def _auth():
        # Push de notificaciones desde otros sistemas: se autentica con X-Notif-Secret (sin sesión)
        if request.path in ("/api/chat/notificaciones", "/api/chat/drive/evento") and request.headers.get("X-Notif-Secret"):
            return None
        if request.path.startswith(_RUTAS_PROTEGIDAS):
            # T-44: enlace de notificación con token (la ventana puede no traer cookie)
            _tok_url = request.args.get("token", "")
            if _tok_url and not session.get("usuario_id"):
                _uid, _correo = sembrar_desde_token(_tok_url)
                if _uid:
                    session["usuario_id"] = _uid
                    session["usuario_correo"] = _correo
                    session["usuario_nombre"] = _cache_nombre.get(_uid, _correo)
                    from flask import redirect as _redirect
                    _limpia = request.path
                    _otros = {k: v for k, v in request.args.items() if k != "token"}
                    if _otros:
                        from urllib.parse import urlencode
                        _limpia += "?" + urlencode(_otros)
                    resp = _redirect(_limpia)
                    resp.set_cookie("access_token", _tok_url, secure=True, samesite="Lax", path="/")
                    return resp
            if session.get("usuario_id"):
                return None
            uid, correo = _resolver_usuario()
            if not uid:
                return _respuesta_no_auth()
            session["usuario_id"] = uid
            session["usuario_correo"] = correo
            session["usuario_nombre"] = _cache_nombre.get(uid, correo)
        # JWT del correo disponible para módulos que consultan el correo en nombre del usuario (calendario)
        _tok = request.cookies.get("access_token") or (request.headers.get("Authorization", "")[7:]
               if request.headers.get("Authorization", "").startswith("Bearer ") else "")
        if _tok and session.get("access_token") != _tok:
            session["access_token"] = _tok
        return None

    return app


application = crear_app()

# Socket.IO (tiempo real). Envuelve la app Flask; gunicorn usa el worker eventlet.
from interfaces.websocket.manejador_websocket import crear_socketio
socketio = crear_socketio(application, redis_url=_REDIS_URL or None)

# Recordatorios de reuniones (10 min antes) por el canal de notificaciones
try:
    from aplicacion.servicios.recordatorios_reuniones import iniciar as _iniciar_recordatorios
    _iniciar_recordatorios(socketio)
except Exception as _e:
    print(f"[recordatorios] no iniciado: {_e}", file=sys.stderr)

if __name__ == "__main__":
    socketio.run(application, host="0.0.0.0", port=int(os.getenv("CHAT_PORT", "8790")))
