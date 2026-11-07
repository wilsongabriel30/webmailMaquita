"""Sondeo de INBOX único por usuario entre los workers (05/11/2026).

Antes, cada worker de uvicorn con una conexión websocket de la misma persona sondeaba su INBOX
cada 45 s con su propio contador en memoria: con dos pestañas (o una reconexión tras un reinicio)
caídas en workers distintos, cada uno detectaba «hay correo nuevo» y publicaba su propio `new_mail`
por Redis, y la página mostraba dos avisos (prueba de humo T-53 intermitente). Además se hacían
hasta 4 sondeos IMAP por persona.

Ahora: un candado en Redis por usuario (`sondeo_inbox:<usuario>`) que toma un solo worker y renueva
en cada vuelta; si ese worker muere o se queda sin conexiones de la persona, lo suelta (o expira) y
otro lo toma. El último conteo (`sondeo_inbox_estado:<usuario>`) vive también en Redis, así el relevo
no dispara un aviso falso. El evento `new_mail` ya llega a todos los workers por el pub/sub de Redis.
"""

import json
import logging
import os

log = logging.getLogger("maquita.webmail.sondeo")

VIGENCIA_CANDADO_S = (
    90  # > 45 s de ciclo + lo que tarde el sondeo (IMAP con tope de 10 s cada paso)
)
VIGENCIA_ESTADO_S = 3600
_ID_WORKER = str(os.getpid())


def _clave(usuario: str) -> str:
    return f"sondeo_inbox:{usuario.lower()}"


def _clave_estado(usuario: str) -> str:
    return f"sondeo_inbox_estado:{usuario.lower()}"


async def tomar(redis, usuario: str) -> bool:
    """True si este worker es (o pasa a ser) el único que sondea a `usuario`."""
    clave = _clave(usuario)
    if await redis.set(clave, _ID_WORKER, nx=True, ex=VIGENCIA_CANDADO_S):
        log.info("sondeo de %s tomado por el worker %s", usuario, _ID_WORKER)
        return True
    dueno = await redis.get(clave)
    if isinstance(dueno, bytes):
        dueno = dueno.decode()
    if dueno == _ID_WORKER:
        await redis.expire(clave, VIGENCIA_CANDADO_S)
        return True
    return False


async def soltar(redis, usuario: str) -> None:
    clave = _clave(usuario)
    dueno = await redis.get(clave)
    if isinstance(dueno, bytes):
        dueno = dueno.decode()
    if dueno == _ID_WORKER:
        await redis.delete(clave)
        log.info("sondeo de %s soltado por el worker %s", usuario, _ID_WORKER)


async def leer_estado(redis, usuario: str) -> int:
    """Último nº de no leídos conocido (en cualquier worker); -1 si no hay."""
    raw = await redis.get(_clave_estado(usuario))
    if not raw:
        return -1
    try:
        return int(json.loads(raw).get("unseen", -1))
    except (ValueError, TypeError, AttributeError):
        return -1


async def guardar_estado(redis, usuario: str, unseen: int, total: int) -> None:
    await redis.set(
        _clave_estado(usuario),
        json.dumps({"unseen": unseen, "total": total}),
        ex=VIGENCIA_ESTADO_S,
    )
