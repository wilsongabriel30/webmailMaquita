"""Índice de las claves de caché de UIDs por carpeta.

Antes, para invalidar la caché tras mover o borrar, se recorría TODO el Redis con SCAN
(unas 900 000 claves, porque el Redis se comparte con Rspamd): ~4 s por cada movimiento.
Ahora cada clave cacheada se anota en un conjunto por carpeta y se borra con un DEL directo.
"""

INDICE = "idx:uids:{username}:{folder}"
VIDA_INDICE = 900  # las claves de UIDs viven 300 s; el índice un poco más


async def registrar_clave(redis, username: str, folder: str, clave: str) -> None:
    """Anota una clave de caché de UIDs en el índice de su carpeta."""
    try:
        indice = INDICE.format(username=username, folder=folder)
        await redis.sadd(indice, clave)
        await redis.expire(indice, VIDA_INDICE)
    except Exception:
        pass


async def invalidar_uids(redis, username: str, *folders: str) -> None:
    """Borra la caché de carpetas/estadísticas y las listas de UIDs de las carpetas dadas."""
    if redis is None:
        return
    try:
        claves = [f"folders:{username}", f"stats:{username}"]
        for folder in folders:
            if not folder:
                continue
            indice = INDICE.format(username=username, folder=folder)
            anotadas = await redis.smembers(indice)
            claves.extend(c.decode() if isinstance(c, bytes) else c for c in anotadas)
            claves.append(indice)
            # Clave del listado sin búsqueda: cubre lo cacheado antes de existir el índice.
            claves.append(f"uids:{username}:{folder}:")
        await redis.delete(*claves)
    except Exception:
        pass
