# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CHAT - SERVICIOS DE APLICACION                            ║
║                     Orquestadores de Casos de Uso                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Servicios disponibles:
- ServicioChat    : Operaciones principales de chat (mensajes, conversaciones)
- ServicioCache   : Operaciones de cache Redis (presencia, typing, mensajes)
- ServicioBusqueda: Busqueda full-text con Elasticsearch
- ServicioIAChat  : Chat con IA Maquita (Ollama LLM)

USO:
    from modulos.chat.aplicacion.servicios import ServicioChat, ServicioCache, ServicioBusqueda
    from modulos.chat.aplicacion.servicios import ServicioIAChat, obtener_servicio_ia_chat

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Actualizado: 2026-01-06 - Agregado ServicioIAChat
"""

from .servicio_chat import ServicioChat, RespuestaChat, ConversacionDTO, MensajeDTO
from .servicio_cache import ServicioCache
from .servicio_busqueda import ServicioBusqueda
from .servicio_ia_chat import (
    ServicioIAChat,
    RespuestaIAChat,
    MensajeIADTO,
    ConversacionIADTO,
    obtener_servicio_ia_chat
)

__all__ = [
    # Chat normal
    'ServicioChat',
    'RespuestaChat',
    'ConversacionDTO',
    'MensajeDTO',
    'ServicioCache',
    'ServicioBusqueda',
    # Chat IA
    'ServicioIAChat',
    'RespuestaIAChat',
    'MensajeIADTO',
    'ConversacionIADTO',
    'obtener_servicio_ia_chat',
]
