# -*- coding: utf-8 -*-
"""
Formularios del Almacén — que vigilar los libros abiertos no ahogue la base
===========================================================================
Cada libro de cálculo abierto en el editor pregunta cada 5 segundos si hay algo
que escribir: el puente de vínculos (`/vinculos/vivo`) y el de respuestas
(`/encuestas/vivo/hojas`). Con **un** libro abierto es un goteo; con diez —lo
normal cuando alguien separa una hoja por provincia— son cuatro consultas por
segundo, y el pool del Almacén (8 conexiones) se queda sin ninguna. Cuando eso
pasa falla CUALQUIER otra cosa del Drive: el 22/09/2026 el listado de carpetas
devolvió 500 y el diálogo «Mover a» se quedó sin lista.

La mayoría de esas preguntas se responden igual una y otra vez: este libro no
tiene ningún formulario ni vínculo que lo alimente. Eso se recuerda un rato y se
contesta sin tocar la base.

  · `recordar_vacio` / `esta_vacio` — la ruta no tenía nada que escribir;
  · cualquier escritura de verdad (una respuesta, un vínculo) llama a `olvidar`
    para que la siguiente pregunta vuelva a mirar la base.

Es una caché por proceso y con caducidad corta. Para que un cambio llegue a
TODOS los procesos al momento (28/09/2026: una respuesta tardó 1:40 en entrar en
el libro abierto porque cinco de los seis workers seguían contestando «nada»),
`olvidar` deja además una marca en Redis y `esta_vacio` la mira: si hubo un
cambio después de anotar «vacío», se vuelve a consultar la base. Si Redis no
responde, se sigue como antes (la caché caduca sola a los 45 s).

Autoría: Equipo de Tecnología Maquita — 2026-09-22
"""
import logging
import os
import threading
import time

SEGUNDOS = 45          # 9 preguntas del puente por cada consulta a la base
CLAVE = 'almacen:vivo:cambio:'

log = logging.getLogger('almacen.vivo_sin_trabajo')
_candado = threading.Lock()
_vacias = {}           # (usuario, ruta) → (cuándo caduca, cuándo se anotó)
_redis = None


def _conexion():
    global _redis
    if _redis is None:
        import redis
        _redis = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
                                      socket_timeout=0.3, socket_connect_timeout=0.3)
    return _redis


def _ultimo_cambio(ruta):
    """Cuándo cambió por última vez esta ruta en cualquier proceso (o 0)."""
    try:
        valores = _conexion().mget([CLAVE + ruta, CLAVE + '*'])
        return max(float(v) for v in valores if v) if any(valores) else 0.0
    except Exception as excepcion:
        log.debug('redis no disponible: %s', excepcion)
        return 0.0


def _anotar_cambio(ruta):
    try:
        _conexion().set(CLAVE + (ruta or '*'), repr(time.time()), ex=SEGUNDOS * 4)
    except Exception as excepcion:
        log.debug('redis no disponible: %s', excepcion)


def esta_vacio(usuario, ruta):
    """¿Consta que esta ruta no tenía nada que escribir?"""
    clave = (int(usuario), ruta)
    with _candado:
        dato = _vacias.get(clave)
        if dato is None:
            return False
        hasta, anotado = dato
        if hasta < time.time():
            _vacias.pop(clave, None)
            return False
    if _ultimo_cambio(ruta) >= anotado:        # cambió en otro proceso
        with _candado:
            _vacias.pop(clave, None)
        return False
    return True


def recordar_vacio(usuario, ruta):
    ahora = time.time()
    with _candado:
        _vacias[(int(usuario), ruta)] = (ahora + SEGUNDOS, ahora)
        if len(_vacias) > 500:                 # no crecer sin fin
            for clave in [c for c, h in _vacias.items() if h[0] < ahora]:
                _vacias.pop(clave, None)


def olvidar(usuario=None, ruta=None):
    """Algo cambió: la próxima pregunta vuelve a mirar la base (en todos los
    procesos, gracias a la marca en Redis)."""
    _anotar_cambio(ruta)
    with _candado:
        if ruta is None:
            _vacias.clear()
            return
        for clave in [c for c in _vacias if c[1] == ruta
                      and (usuario is None or c[0] == int(usuario))]:
            _vacias.pop(clave, None)
