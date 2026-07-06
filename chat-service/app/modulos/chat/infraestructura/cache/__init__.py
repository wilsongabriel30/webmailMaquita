# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     CHAT - IMPLEMENTACIONES DE CACHE                         ║
║                            Redis como Backend                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

██████████████████████████████████████████████████████████████████████████████
██  REGLAS PARA ESTA CAPA (APLICA A TODOS LOS MODULOS)                       ██
██████████████████████████████████████████████████████████████████████████████

1. RESPONSABILIDADES:
   - Implementar interfaces de dominio/repositorios/repositorio_cache.py
   - Manejar conexion a Redis
   - Serializar/deserializar datos
   - Gestionar TTL y expiracion

2. DEPENDENCIAS PERMITIDAS:
   - dominio/ (interfaces y entidades)
   - redis, json, pickle (tecnologias de cache)

3. DEPENDENCIAS PROHIBIDAS:
   - Flask (va en interfaces/)
   - SQLAlchemy (va en persistencia/)
   - aplicacion/ (no debe conocer casos de uso)

4. PREFIJOS DE CLAVES REDIS:
   - chat:msg:{conv_id}        -> Mensajes de conversacion
   - chat:presence:{user_id}   -> Presencia de usuario
   - chat:typing:{conv_id}     -> Indicadores de escritura
   - chat:conv:{conv_id}       -> Metadata de conversacion
   - chat:ws:{user_id}         -> Sesiones WebSocket
   - chat:unread:{user}:{conv} -> Contadores no leidos

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

from .cliente_redis import ClienteRedis, obtener_cliente_redis
from .cache_mensajes import CacheMensajesRedis
from .cache_presencia import CachePresenciaRedis
from .cache_indicador import CacheIndicadorAccionRedis
from .cache_conversacion import CacheConversacionRedis
from .cache_sesion import CacheSesionWebSocketRedis

__all__ = [
    # Cliente base
    'ClienteRedis',
    'obtener_cliente_redis',
    # Implementaciones
    'CacheMensajesRedis',
    'CachePresenciaRedis',
    'CacheIndicadorAccionRedis',
    'CacheConversacionRedis',
    'CacheSesionWebSocketRedis',
]
