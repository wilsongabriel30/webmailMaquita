"""Contadores de envío send_rl:* en Redis (quién está cerca del límite de envío)."""
import redis

from . import config
from .hallazgo import Hallazgo, MEDIO, INFO
from .nombres import a_quien_preguntar


def contadores():
    cli = redis.Redis.from_url(config.url_redis(), decode_responses=True, socket_timeout=5)
    filas = []
    for clave in cli.scan_iter('send_rl:*'):
        try:
            _, ventana, usuario = clave.split(':', 2)
            filas.append((ventana, usuario, int(cli.get(clave) or 0), cli.ttl(clave)))
        except (ValueError, redis.RedisError):
            continue
    return filas


def hallazgos(limite_hora=20, limite_dia=100):
    salida = []
    try:
        filas = contadores()
    except redis.RedisError as e:
        return [Hallazgo(MEDIO, 'e', f'No se pudo leer Redis: {e}', '', [], 'Revisar el servicio redis y REDIS_URL.')]
    for ventana, usuario, n, ttl in filas:
        tope = limite_hora if ventana == 'hour' else limite_dia if ventana == 'day' else None
        if tope and n >= tope * 0.8:
            salida.append(Hallazgo(
                MEDIO, 'e', f'Contador de envío {ventana} = {n} (tope orientativo {tope})', usuario,
                [f'clave send_rl:{ventana}:{usuario}, caduca en {ttl} s'],
                a_quien_preguntar(usuario) + ' Verificar si es envío masivo legítimo o un bucle de reintentos.',
            ))
    return salida, filas
