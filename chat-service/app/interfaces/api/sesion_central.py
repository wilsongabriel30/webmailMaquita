# -*- coding: utf-8 -*-
"""La sesión CENTRAL del correo dentro del chat (F-03, tercera revisión ASVS).

El chat tiene su propia cookie (`chat_session`) y su propio Redis: no puede mirar el
estado del correo. Por eso la regla de sesión se aplica con tres piezas:

1. El vale de entrada trae `sid` y `av` (generación) del correo; quedan en la sesión.
2. El correo EMPUJA cada revocación a `POST /api/chat/sesion/revocar` (secreto compartido
   `X-Notif-Secret`, con límite de peticiones). Aquí se anota en Redis (o en memoria si
   no hay Redis) y se desconectan los Socket.IO afectados.
3. Cada petición compara la generación anotada; y cada `REVALIDAR_SEG` la sesión vuelve a
   preguntar al correo (`GET /api/auth/sesion-servicio`). Si el correo no responde,
   FALLO CERRADO: el chat ya depende del correo para todo lo demás.

Riesgo residual (DECISIONES.md D-4): entre la revocación central y la revalidación (máx.
REVALIDAR_SEG) el chat depende del empuje; si el empuje falla, el correo lo registra con
ERROR y marca REVOCACION_CHAT_FALLIDA, nunca en silencio.
"""
import hmac
import os
import sys
import threading
import time

from flask import Blueprint, jsonify, request, session

bp_sesion = Blueprint("sesion_central", __name__, url_prefix="/api/chat/sesion")

REVALIDAR_SEG = int(os.getenv("CHAT_REVALIDAR_SESION_SEG", "300"))
TTL_REVOCACION = 86400
LIMITE_REVOCAR_POR_MIN = int(os.getenv("CHAT_REVOCAR_LIMITE_MIN", "60"))

# Quién resuelve correo -> id de usuario. Lo fija app_chat al registrar el blueprint.
resolver_uid = None

_memoria = {}
_contador = {}
_lock = threading.Lock()


def _correo_url() -> str:
    return (os.getenv("CORREO_URL_API") or os.getenv("CORREO_URL_CALENDARIO") or "").rstrip("/")


# ----------------------------------------------------------------- almacén (Redis o memoria)
def _redis():
    try:
        from modulos.chat.infraestructura.cache.cliente_redis import obtener_cliente_redis

        r = obtener_cliente_redis()
        return r if r.disponible else None
    except Exception:
        return None


def _poner(clave: str, valor, ttl: int) -> None:
    r = _redis()
    if r is not None:
        try:
            r.set(clave, str(valor), ttl_segundos=ttl)
            return
        except Exception:
            pass
    with _lock:
        _memoria[clave] = (str(valor), time.time() + ttl)


def _leer(clave: str):
    r = _redis()
    if r is not None:
        try:
            v = r.get(clave)
            if v is not None:
                return v.decode() if isinstance(v, bytes) else v
        except Exception:
            pass
    with _lock:
        v = _memoria.get(clave)
        if not v:
            return None
        if v[1] < time.time():
            _memoria.pop(clave, None)
            return None
        return v[0]


# ----------------------------------------------------------------- revocación
def registrar_revocacion(uid: int, sid: str, av: int) -> None:
    """Anota lo que el correo revocó: un sid concreto, o todo el usuario hasta la generación av."""
    if sid == "*":
        _poner(f"chat:revocado:{uid}", int(av or 0), TTL_REVOCACION)
    else:
        _poner(f"chat:revocado_sid:{sid}", "1", TTL_REVOCACION)


def sesion_revocada(uid, sid, av) -> bool:
    if sid and _leer(f"chat:revocado_sid:{sid}"):
        return True
    v = _leer(f"chat:revocado:{uid}")
    if v is None:
        return False
    try:
        return int(av or 0) < int(v)
    except (TypeError, ValueError):
        return True


def _revalidar_con_correo(correo: str, sid: str):
    """True/False según el correo; None si no se pudo saber (se trata como no válida)."""
    base = _correo_url()
    if not base or not sid or not correo:
        return None
    try:
        import requests as _rq

        r = _rq.get(
            f"{base}/api/auth/sesion-servicio",
            params={"user": correo, "sid": sid},
            headers={"X-Notif-Secret": os.getenv("NOTIF_SECRET", "")},
            timeout=4,
        )
        if r.status_code != 200:
            return None
        return bool((r.json() or {}).get("valida"))
    except Exception:
        return None


def sesion_central_valida() -> bool:
    """La regla única, vista desde el chat. Deja la sesión limpia cuando no vale."""
    uid = session.get("usuario_id")
    sid = session.get("sid")
    av = session.get("av")
    if not uid:
        return False
    if not sid or av is None:
        # Sesión anterior al modelo sid/av: hay que volver a entrar por el correo.
        return False
    if sesion_revocada(uid, sid, av):
        return False
    if time.time() > float(session.get("validado_hasta") or 0):
        ok = _revalidar_con_correo(session.get("usuario_correo", ""), sid)
        if ok is None:
            print(
                "[chat] SESION_NO_REVALIDABLE usuario=%s sid=%s: el correo no responde; "
                "fallo cerrado" % (uid, sid[:8]),
                file=sys.stderr,
            )
            return False
        if not ok:
            registrar_revocacion(uid, sid, av)
            return False
        session["validado_hasta"] = time.time() + REVALIDAR_SEG
    return True


def desconectar_sockets(uid: int, sid: str) -> int:
    """Cierra los Socket.IO del usuario (todos, o los de una sesión del correo)."""
    try:
        from interfaces.websocket import manejador_websocket as mw
    except Exception:
        return 0
    n = 0
    for ssid in list(mw.usuarios_conectados.get(uid, set())):
        if sid != "*" and mw.sesion_de_socket.get(ssid) != sid:
            continue
        try:
            mw.socketio.server.disconnect(ssid, namespace="/")
            n += 1
        except Exception as e:
            print(f"[chat] no se pudo desconectar {ssid}: {e}", file=sys.stderr)
    return n


# ----------------------------------------------------------------- endpoint que llama el correo
def _permitido(ip: str) -> bool:
    ventana = int(time.time() // 60)
    clave = f"{ip}:{ventana}"
    with _lock:
        n = _contador.get(clave, 0) + 1
        _contador[clave] = n
        if len(_contador) > 1000:
            for k in [k for k in _contador if not k.endswith(f":{ventana}")]:
                _contador.pop(k, None)
    return n <= LIMITE_REVOCAR_POR_MIN


@bp_sesion.route("/revocar", methods=["POST"])
def revocar():
    secreto = os.getenv("NOTIF_SECRET", "")
    recibido = request.headers.get("X-Notif-Secret", "")
    if not secreto or not hmac.compare_digest(secreto, recibido):
        return jsonify({"success": False, "error": "No autorizado"}), 403
    ip = request.headers.get("X-Real-IP", request.remote_addr or "?")
    if not _permitido(ip):
        return jsonify({"success": False, "error": "Demasiadas peticiones"}), 429
    d = request.get_json(silent=True) or {}
    correo = (d.get("user") or "").strip().lower()
    sid = str(d.get("sid") or "*")
    try:
        av = int(d.get("av") or 0)
    except (TypeError, ValueError):
        av = 0
    if not correo:
        return jsonify({"success": False, "error": "Falta user"}), 400
    uid = resolver_uid(correo) if resolver_uid else None
    if not uid:
        return jsonify({"success": True, "usuario": False, "desconectados": 0})
    registrar_revocacion(uid, sid, av)
    n = desconectar_sockets(uid, sid)
    print(f"[chat] REVOCACION usuario={uid} sid={sid[:8]} av={av} desconectados={n}", file=sys.stderr)
    return jsonify({"success": True, "usuario": True, "desconectados": n})
