# -*- coding: utf-8 -*-
"""
Avisos entre procesos del Drive, por Redis (28/09/2026)
======================================================
El Drive corre en varios procesos (workers). Lo que uno anota en memoria, los
demás no lo ven. Para los avisos que tienen que llegar a todos —«esta copia se
acaba de actualizar»— se usa el Redis que Raíces ya tiene para el chat.

Nunca falla hacia fuera: si Redis no responde, `leer` devuelve None y `poner`
no hace nada. Quien lo usa debe funcionar igual, solo que sin el aviso.

Autoría: Equipo de Tecnología Maquita — 2026-09-28
"""
import logging
import os

log = logging.getLogger('almacen.avisos_redis')

PREFIJO = 'almacen:aviso:'
_redis = None


def _conexion():
    global _redis
    if _redis is None:
        import redis
        _redis = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
                                      socket_timeout=0.3, socket_connect_timeout=0.3,
                                      decode_responses=True)
    return _redis


def poner(clave, valor, segundos):
    try:
        _conexion().set(PREFIJO + clave, str(valor), ex=int(segundos))
    except Exception as excepcion:
        log.debug('redis no disponible: %s', excepcion)


def leer(clave):
    try:
        return _conexion().get(PREFIJO + clave)
    except Exception as excepcion:
        log.debug('redis no disponible: %s', excepcion)
        return None
