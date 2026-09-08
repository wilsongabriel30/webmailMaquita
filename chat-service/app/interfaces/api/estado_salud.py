# -*- coding: utf-8 -*-
"""`/healthz` distingue «el proceso vive» de «puede tocar su base» (aviso de Andes, 08/09/2026).

A Andes les pasó de verdad: su chat llevaba semanas respondiendo 200 con las tablas `chat_*` sin
crear, y cualquier petición real devolvía «Error interno del servidor». Un healthz que solo dice
que el proceso arrancó no sirve para vigilar: lo verde tapaba una instalación a medias.

Ahora responde:
  200 {"estado": "ok", "base": "ok"}                       todo en su sitio
  503 {"estado": "degradado", "base": "sin_tablas"}        conecta, faltan las tablas del chat
  503 {"estado": "degradado", "base": "sin_conexion"}      no llega a la base
"""
import time

_CACHE_SEG = 5
_ultimo = {"t": 0.0, "base": None, "detalle": ""}

FALTAN_TABLAS = "sin_tablas"
SIN_CONEXION = "sin_conexion"
CORRECTO = "ok"

# La tabla mínima sin la que el chat no puede hacer nada.
_SONDA = "SELECT to_regclass('public.chat_conversations') IS NOT NULL"


def revisar_base(ejecutar, ahora=None) -> tuple:
    """(estado, detalle). `ejecutar(sql)` devuelve un escalar o revienta.

    Se recuerda unos segundos: el healthz lo consultan vigilantes cada poco y no tiene sentido
    preguntar a la base en cada llamada.
    """
    t = ahora if ahora is not None else time.time()
    if _ultimo["base"] is not None and t - _ultimo["t"] < _CACHE_SEG:
        return _ultimo["base"], _ultimo["detalle"]
    try:
        hay = bool(ejecutar(_SONDA))
        estado = CORRECTO if hay else FALTAN_TABLAS
        detalle = "" if hay else ("faltan las tablas del chat: ejecuta migrar_chat.py "
                                  "(ver docs/CHAT-INSTALACION.md)")
    except Exception as e:
        estado, detalle = SIN_CONEXION, ("no se pudo consultar la base: %s" % type(e).__name__)
    _ultimo.update({"t": t, "base": estado, "detalle": detalle})
    return estado, detalle


def olvidar_cache():
    _ultimo.update({"t": 0.0, "base": None, "detalle": ""})


def respuesta(servicio, chat_montado, estado_base, detalle) -> tuple:
    """(cuerpo, código). 200 solo si la base está utilizable."""
    ok = estado_base == CORRECTO
    cuerpo = {
        "success": ok,               # se conserva por compatibilidad con lo que ya vigilaba
        "estado": "ok" if ok else "degradado",
        "servicio": servicio,
        "chat_montado": bool(chat_montado),
        "base": estado_base,
    }
    if detalle:
        cuerpo["detalle"] = detalle
    return cuerpo, (200 if ok else 503)
