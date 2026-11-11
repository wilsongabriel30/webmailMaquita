"""Un borrador, una sola copia (11/11/2026).

Guardar un borrador es «añadir el nuevo y borrar el anterior» y cada guardado devuelve un UID nuevo.
Si dos guardados salen casi a la vez (dos rutas de la interfaz, dos pestañas, la aplicación y el
navegador), el segundo llega con el UID viejo o sin UID: borraba algo que ya no existía y quedaban
dos borradores iguales (reportado por varias personas; en el registro, dos POST a 200 ms).

Aquí el servidor lo resuelve sin depender del cliente:
  * un candado por persona hace que los guardados de borrador pasen de uno en uno;
  * se recuerda por qué UID fue reemplazado cada borrador (un día), y un UID viejo se traduce al vigente;
  * un borrador «nuevo» igual (asunto, destinatarios y respuesta-a) a otro creado hace segundos
    reemplaza a ese en vez de duplicarlo.
Si Redis no responde, se guarda como antes: nunca se pierde un borrador por esto.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
from contextlib import asynccontextmanager

logger = logging.getLogger("maquita.webmail.borradores")

TTL_CADENA_S = 86400
TTL_NUEVO_S = 20
CANDADO_MS = 20000
ESPERA_MAX_S = 6.0
MAX_SALTOS = 30


def _texto(v) -> str:
    return v.decode() if isinstance(v, (bytes, bytearray)) else (v or "")


@asynccontextmanager
async def candado(redis, usuario: str):
    """Guardados de borrador de la misma persona, de uno en uno (como mucho se espera 6 s)."""
    clave, ficha, mio = f"borrador:candado:{usuario}", secrets.token_hex(8), False
    try:
        fin = asyncio.get_running_loop().time() + ESPERA_MAX_S
        while True:
            if await redis.set(clave, ficha, nx=True, px=CANDADO_MS):
                mio = True
                break
            if asyncio.get_running_loop().time() >= fin:
                break
            await asyncio.sleep(0.05)
    except Exception as exc:
        logger.warning("borradores: sin candado (%s); se guarda igual", exc)
    try:
        yield
    finally:
        if mio:
            try:
                if _texto(await redis.get(clave)) == ficha:
                    await redis.delete(clave)
            except Exception:
                pass


async def vigente(redis, usuario: str, uid: int | None) -> int | None:
    """El UID que hoy ocupa el lugar de `uid` (el mismo si nadie lo reemplazó)."""
    if not uid:
        return None
    actual = int(uid)
    try:
        for _ in range(MAX_SALTOS):
            siguiente = _texto(await redis.get(f"borrador:sig:{usuario}:{actual}"))
            if not siguiente.isdigit() or int(siguiente) == actual:
                break
            actual = int(siguiente)
    except Exception:
        return int(uid)
    return actual


def huella(asunto: str, para: list[str] | None, en_respuesta_a: str | None) -> str:
    base = "\x1f".join(
        [
            (asunto or "").strip(),
            ",".join(sorted(p.strip().lower() for p in para or [])),
            (en_respuesta_a or "").strip(),
        ]
    )
    return hashlib.sha256(base.encode()).hexdigest()[:32]


async def recien_creado(redis, usuario: str, marca: str) -> int | None:
    """UID de un borrador igual que esta persona creó hace segundos (para no duplicarlo)."""
    try:
        v = _texto(await redis.get(f"borrador:nuevo:{usuario}:{marca}"))
        return int(v) if v.isdigit() else None
    except Exception:
        return None


async def anotar(
    redis, usuario: str, marca: str, nuevo: int | None, *anteriores: int | None
) -> None:
    """Deja escrito que `nuevo` reemplaza a los `anteriores` y que es el último con esa huella."""
    if not nuevo:
        return
    try:
        for viejo in {int(a) for a in anteriores if a}:
            if viejo != nuevo:
                await redis.set(
                    f"borrador:sig:{usuario}:{viejo}", str(nuevo), ex=TTL_CADENA_S
                )
        await redis.set(f"borrador:nuevo:{usuario}:{marca}", str(nuevo), ex=TTL_NUEVO_S)
    except Exception as exc:
        logger.warning("borradores: no se pudo anotar el reemplazo: %s", exc)
