# -*- coding: utf-8 -*-
"""Mensajes: punto de entrada. Partido el 28/08/2026 en módulos por responsabilidad (sin cambios en rutas):
#   chat_mensajes_obtener.py  (11-281): Mensajes: listar (GET) con paginación.
#   chat_mensajes_enviar.py  (282-570): Mensajes: enviar (POST).
#   chat_mensajes_editar.py  (571-758): Mensajes: editar, eliminar y limpiar conversación.
#   chat_mensajes_leidos.py  (759-829): Mensajes: marcar conversación como leída.
"""
from interfaces.api.chat_base import *  # noqa: F401,F403
from interfaces.api.chat_mensajes_obtener import *  # noqa: F401,F403,E402
from interfaces.api.chat_mensajes_enviar import *  # noqa: F401,F403,E402
from interfaces.api.chat_mensajes_editar import *  # noqa: F401,F403,E402
from interfaces.api.chat_mensajes_leidos import *  # noqa: F401,F403,E402
import interfaces.api.chat_mensajes_obtener  # noqa: F401,E402
import interfaces.api.chat_mensajes_enviar  # noqa: F401,E402
import interfaces.api.chat_mensajes_editar  # noqa: F401,E402
import interfaces.api.chat_mensajes_leidos  # noqa: F401,E402
