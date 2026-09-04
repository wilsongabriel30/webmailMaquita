# -*- coding: utf-8 -*-
"""Mensajería por WebSocket: punto de entrada. Partido el 28/08/2026 en módulos por responsabilidad (mismos eventos):
#   ws_salas.py, ws_mensajes.py, ws_escribiendo.py: manejadores base (devuelven sus funciones)
#   ws_canal_rapido.py (send), ws_canal_rapido_alias.py (join/leave/typing/read/ping_chat), ws_escribiendo_expira.py (typing_with_expire)
"""
from interfaces.websocket import ws_salas, ws_mensajes, ws_escribiendo, ws_canal_rapido, ws_canal_rapido_alias, ws_escribiendo_expira


def registrar(socketio):
    base = {}
    for modulo in (ws_salas, ws_mensajes, ws_escribiendo):
        base.update(modulo.registrar(socketio))
    ws_canal_rapido.registrar(socketio, base)
    ws_canal_rapido_alias.registrar(socketio, base)
    ws_escribiendo_expira.registrar(socketio)
