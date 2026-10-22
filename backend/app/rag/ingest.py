"""Ingesta incremental de la bandeja de un usuario al índice RAG.

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
from app.rag import store
from app.rag.embeddings import embed

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


async def ingest_user(db, username, limit=None, redis=None):
    """Indexa la bandeja. Devuelve {indexed, total, leidos, errores, ...}."""
    if limit is None:
        limit = int(os.getenv("RAG_INGEST_LIMIT", "3000"))
    por_tanda = max(20, int(os.getenv("RAG_INGEST_PAGE", "150")))
    if not await rag_config.domain_enabled(db, username):
        return {"username": username, "skipped": "dominio no habilitado", "indexed": 0}
    await store.ensure_schema(db)
    s = get_settings()
    from app.mail.clients.imap_client import get_imap_connection
    from app.mail.services.message_service import list_messages

    estado = {
        "estado": "en_curso",
        "inicio": time.time(),
        "leidos": 0,
        "indexed": 0,
        "errores": 0,
        "mensaje": "",
    }
    _PROGRESO[username] = estado
    await _publicar(redis, username, estado)

    try:
        imap = await get_imap_connection(f"{username}*admin", s.master_password)
    except Exception as e:
        estado.update(estado="error", mensaje=f"No se pudo abrir el buzón (IMAP): {e}")
        await _publicar(redis, username, estado)
        return {"username": username, "error": estado["mensaje"], "indexed": 0}

    have = await store.existing_uids(db, username)
    msgs: list[dict] = []
    try:
        pagina = 1
        while len(msgs) < limit:
            try:
                res = await list_messages(imap, "INBOX", pagina, por_tanda, "")
            except (
                Exception
            ) as e:  # CommandTimeout u otro fallo de una tanda: se anota y se sigue
                estado["errores"] += 1
                logger.warning("RAG %s: tanda %s falló: %s", username, pagina, e)
                if estado["errores"] >= 3:
                    break
                pagina += 1
                continue
            tanda = (res or {}).get("messages", []) if res else []
            if not tanda:
                break
            msgs.extend(tanda)
            estado["leidos"] = len(msgs)
            await _publicar(redis, username, estado)
            if len(tanda) < por_tanda:
                break
            pagina += 1
    finally:
        try:
            await imap.logout()
        except Exception:
            pass

    indexed = 0
    for m in msgs[:limit]:
        uid = str(m.get("uid", ""))
        if not uid or uid in have:
            continue
        content = f"De: {m.get('from','')} | Asunto: {m.get('subject','')} | {m.get('snippet','')}"
        emb = await embed(content)
        if not emb:
            estado["errores"] += 1
            continue
        await store.upsert(
            db,
            username,
            "INBOX",
            uid,
            m.get("subject", ""),
            m.get("from", ""),
            content,
            emb,
        )
        indexed += 1
        estado["indexed"] = indexed
        if indexed % 25 == 0:
            await _publicar(redis, username, estado)
    total = await store.count(db, username)
    if not msgs and estado["errores"]:
        estado.update(
            estado="error",
            mensaje="El buzón no respondió a tiempo al leer los correos. Vuelve a intentarlo en unos minutos.",
        )
    else:
        estado.update(estado="listo", mensaje="")
    estado["total"] = total
    await _publicar(redis, username, estado)
    return {
        "username": username,
        "indexed": indexed,
        "leidos": len(msgs),
        "errores": estado["errores"],
        "total": total,
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
