# -*- coding: utf-8 -*-
"""Limitador de eventos del socket (L-04 de la quinta revisión, Alice).

Con Redis el conteo es compartido entre procesos. Sin Redis (o si Redis falla a mitad) cada
proceso solo ve su parte, así que antes el tope real se multiplicaba por el número de workers
y el fallo pasaba en silencio. Ahora, como R-2 en el correo: sin Redis se aplica un **tope
conservador** (el configurado dividido por FACTOR_SIN_REDIS, mínimo 1) y se registra ERROR con
la marca `RATE_LIMIT_SIN_REDIS` (una vez por minuto, no por evento).
"""
import logging
import threading
import time
from collections import defaultdict

log = logging.getLogger("seguridad.chat.limitador")

FACTOR_SIN_REDIS = 4
_AVISO_CADA = 60


class Limitador:
    """Contador por clave en ventana fija. `redis` es el envoltorio del chat (incr/expire) o None."""

    def __init__(self, redis=None):
        self._requests = defaultdict(list)
        self._lock = threading.Lock()
        self._redis = redis
        self._ultimo_aviso = 0.0

    @property
    def con_redis(self):
        return self._redis is not None

    def _avisar_sin_redis(self, motivo):
        ahora = time.time()
        if ahora - self._ultimo_aviso >= _AVISO_CADA:
            self._ultimo_aviso = ahora
            log.error(
                "RATE_LIMIT_SIN_REDIS: límite por proceso y dividido por %s (%s)",
                FACTOR_SIN_REDIS,
                motivo,
            )

    def is_allowed(self, key, max_requests, window_seconds):
        if self._redis is not None:
            try:
                redis_key = f"chat:rate:{key}"
                count = self._redis.incr(redis_key)
                if count == 1:
                    self._redis.expire(redis_key, window_seconds)
                return count <= max_requests
            except Exception as exc:
                self._avisar_sin_redis(f"error de Redis: {str(exc)[:80]}")
        else:
            self._avisar_sin_redis("Redis no disponible")
        tope = max(1, int(max_requests) // FACTOR_SIN_REDIS)
        now = time.time()
        with self._lock:
            vivos = [t for t in self._requests[key] if now - t < window_seconds]
            self._requests[key] = vivos
            if len(vivos) >= tope:
                return False
            vivos.append(now)
            return True

    def cleanup(self):
        now = time.time()
        with self._lock:
            for key in [k for k, ts in self._requests.items() if not any(now - t < 60 for t in ts)]:
                del self._requests[key]
