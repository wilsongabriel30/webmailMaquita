"""Ingesta incremental del buzón de un usuario al índice RAG (todas las carpetas).

04/11/2026: ya no es solo la Bandeja de entrada: se indexan todas las carpetas salvo
Papelera, Spam y Borradores (app.rag.indexador / carpetas), con el inicio del cuerpo.

19/10/2026: antes se pedían los 3000 correos en un solo UID FETCH y Dovecot no contestaba a
tiempo (aioimaplib CommandTimeout) → el botón «Sincronizar mi bandeja» devolvía 500 sin aviso.
Ahora se lee por tandas (RAG_INGEST_PAGE) y, si una tanda falla, se registra y se sigue con la
siguiente; los correos ya indexados no se vuelven a pedir a la IA. El progreso queda en
`progreso()` para que la pantalla lo muestre mientras la sincronización corre en segundo plano.
"""

import asyncio
import json
import logging
import os
import time

from app.config import get_settings
from app.rag import config as rag_config
from app.rag import indexador, plan, store

logger = logging.getLogger(__name__)

# Estado por usuario. Se guarda en este proceso y, si hay Redis, también allí: con varios
# workers o varias máquinas, la consulta de /status puede caer en otro proceso que el que
# corre la sincronización y antes veía «nada en curso» (y dejaba lanzar otra a la vez).
_PROGRESO: dict[str, dict] = {}
CLAVE_REDIS = "rag:progreso:{}"
TTL_PROGRESO_S = 6 * 3600  # una sincronización colgada no bloquea para siempre


def progreso(username: str) -> dict | None:
    """Estado de la última sincronización lanzada en este proceso para el usuario."""
    return _PROGRESO.get(username)


def en_curso(username: str) -> bool:
    p = _PROGRESO.get(username)
    return bool(p and p.get("estado") == "en_curso")


async def _publicar(redis, username: str, estado: dict) -> None:
    """Copia el progreso a Redis (si lo hay) para que lo vean los demás procesos."""
    if redis is None:
        return
    try:
        await redis.set(
            CLAVE_REDIS.format(username), json.dumps(estado), ex=TTL_PROGRESO_S
        )
    except Exception as e:
        logger.debug("RAG %s: no se pudo publicar el progreso: %s", username, e)


async def progreso_compartido(username: str, redis=None) -> dict | None:
    """Progreso visto desde cualquier proceso: Redis primero, memoria si no hay Redis."""
    if redis is not None:
        try:
            crudo = await redis.get(CLAVE_REDIS.format(username))
            if crudo:
                return json.loads(crudo)
        except Exception:
            pass
    return progreso(username)


async def ingest_user(db, username, limit=None, redis=None, presupuesto=None):
    """Indexa todas las carpetas del buzón (ver indexador). Devuelve {indexed, total, ...}.

    `limit`: correos como máximo en esta ejecución para este buzón (RAG_INGEST_LIMIT, 3000 por
    omisión: el botón «Sincronizar» avanza a tandas y la tarea nocturna continúa). 0 = sin
    límite. `presupuesto`: límite global de la ejecución nocturna (plan.Presupuesto).
    """
    if limit is None:
        limit = int(os.getenv("RAG_INGEST_LIMIT", "3000"))
    if presupuesto is None:
        presupuesto = plan.Presupuesto()
    if not await rag_config.domain_enabled(db, username):
        return {"username": username, "skipped": "dominio no habilitado", "indexed": 0}
    s = get_settings()
    from app.mail.clients.imap_client import get_imap_connection

    estado = {
        "estado": "en_curso",
        "inicio": time.time(),
        "leidos": 0,
        "indexed": 0,
        "errores": 0,
        "mensaje": "",
        "carpeta": "",
        "carpetas_hechas": 0,
        "carpetas_total": 0,
        "pendientes": 0,
    }
    _PROGRESO[username] = estado
    await _publicar(redis, username, estado)

    async def conectar():
        return await get_imap_connection(f"{username}*admin", s.master_password)

    async def publicar():
        await _publicar(redis, username, estado)

    resultado = {"completo": False}
    try:
        resultado = await indexador.indexar_buzon(
            db, username, conectar, estado, publicar, limit, presupuesto
        )
    except indexador.EmbeddingsCaidos:
        estado.update(
            estado="error",
            mensaje="El servicio de IA que prepara los correos no responde. Vuelve a intentarlo más tarde.",
        )
    except Exception as e:
        logger.warning("RAG %s: no se pudo indexar: %s", username, e)
        estado.update(estado="error", mensaje=f"No se pudo abrir el buzón (IMAP): {e}")
    total = await store.count(db, username)
    if estado["estado"] != "error":
        if not estado["indexed"] and not estado["leidos"] and estado["errores"]:
            estado.update(
                estado="error",
                mensaje="El buzón no respondió a tiempo al leer los correos. Vuelve a intentarlo en unos minutos.",
            )
        else:
            estado.update(estado="listo", mensaje="")
    estado["total"] = total
    estado["carpeta"] = ""
    await _publicar(redis, username, estado)
    return {
        "username": username,
        "indexed": estado["indexed"],
        "leidos": estado["leidos"],
        "errores": estado["errores"],
        "total": total,
        "pendientes": estado.get("pendientes", 0),
        "incompleto": not resultado.get("completo"),
        "embeddings_caidos": estado["mensaje"].startswith("El servicio de IA"),
        "error": estado["mensaje"] or None,
    }


async def lanzar_en_segundo_plano(db, username, redis=None) -> bool:
    """Arranca la ingesta sin bloquear la petición. False si ya hay una en curso
    (en este proceso o, con Redis, en cualquier otro)."""
    if en_curso(username):
        return False
    previo = await progreso_compartido(username, redis)
    if previo and previo.get("estado") == "en_curso":
        return False
    _PROGRESO[username] = {
        "estado": "en_curso",
        "inicio": time.time(),
        "leidos": 0,
        "indexed": 0,
        "errores": 0,
        "mensaje": "",
    }
    await _publicar(redis, username, _PROGRESO[username])

    async def _correr():
        try:
            await ingest_user(db, username, redis=redis)
        except Exception as e:  # nunca dejar el estado colgado en «en_curso»
            logger.exception("RAG %s: sincronización falló", username)
            _PROGRESO[username] = {
                "estado": "error",
                "inicio": time.time(),
                "leidos": 0,
                "indexed": 0,
                "errores": 1,
                "mensaje": f"La sincronización falló: {e}",
            }
            await _publicar(redis, username, _PROGRESO[username])

    asyncio.get_running_loop().create_task(_correr())
    return True
