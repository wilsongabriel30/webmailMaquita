"""Límites de T-74 en Redis (ventana fija). Si Redis falla no se bloquea a nadie: el código de un
solo uso y su caducidad ya protegen; el límite solo frena abusos.

    alta-equipo: 5 por hora y persona; 2 clientes NUEVOS por persona y día
    canjear:     20 por hora y dirección IP (desde las sedes salen varios equipos por la misma IP)
"""

ALTA_POR_HORA = 5
NUEVOS_POR_DIA = 2
CANJES_POR_HORA_IP = 20


async def _contar(redis, clave: str, ventana_s: int) -> int:
    try:
        n = await redis.incr(clave)
        if n == 1:
            await redis.expire(clave, ventana_s)
        return int(n)
    except Exception:
        return 0


async def alta_superada(redis, user_email: str) -> bool:
    return await _contar(redis, f"respaldos:alta:{user_email}", 3600) > ALTA_POR_HORA


async def nuevos_superados(redis, user_email: str) -> bool:
    return (
        await _contar(redis, f"respaldos:nuevos:{user_email}", 86400) > NUEVOS_POR_DIA
    )


async def canje_superado(redis, ip: str) -> bool:
    return await _contar(redis, f"respaldos:canje:{ip}", 3600) > CANJES_POR_HORA_IP
