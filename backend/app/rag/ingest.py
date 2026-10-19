"""Ingesta incremental de la bandeja de un usuario al índice RAG.

19/10/2026: antes se pedían los 3000 correos en un solo UID FETCH y Dovecot no contestaba a
tiempo (aioimaplib CommandTimeout) → el botón «Sincronizar mi bandeja» devolvía 500 sin aviso.
Ahora se lee por tandas (RAG_INGEST_PAGE) y, si una tanda falla, se registra y se sigue con la
siguiente; los correos ya indexados no se vuelven a pedir a la IA. El progreso queda en
`progreso()` para que la pantalla lo muestre mientras la sincronización corre en segundo plano.
"""

import asyncio
import logging
import os
import time

from app.config import get_settings
from app.rag import config as rag_config
from app.rag import store
from app.rag.embeddings import embed

logger = logging.getLogger(__name__)

# Estado en memoria por usuario (una instancia del backend). Suficiente para informar a la
# pantalla; si hay varios workers, cada uno ve solo sus propias sincronizaciones.
_PROGRESO: dict[str, dict] = {}


def progreso(username: str) -> dict | None:
    """Estado de la última sincronización lanzada en este proceso para el usuario."""
    return _PROGRESO.get(username)


def en_curso(username: str) -> bool:
    p = _PROGRESO.get(username)
    return bool(p and p.get("estado") == "en_curso")


async def ingest_user(db, username, limit=None):
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

    try:
        imap = await get_imap_connection(f"{username}*admin", s.master_password)
    except Exception as e:
        estado.update(estado="error", mensaje=f"No se pudo abrir el buzón (IMAP): {e}")
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
    total = await store.count(db, username)
    if not msgs and estado["errores"]:
        estado.update(
            estado="error",
            mensaje="El buzón no respondió a tiempo al leer los correos. Vuelve a intentarlo en unos minutos.",
        )
    else:
        estado.update(estado="listo", mensaje="")
    estado["total"] = total
    return {
        "username": username,
        "indexed": indexed,
        "leidos": len(msgs),
        "errores": estado["errores"],
        "total": total,
        "error": estado["mensaje"] or None,
    }


def lanzar_en_segundo_plano(db, username) -> bool:
    """Arranca la ingesta sin bloquear la petición. False si ya hay una en curso."""
    if en_curso(username):
        return False
    _PROGRESO[username] = {
        "estado": "en_curso",
        "inicio": time.time(),
        "leidos": 0,
        "indexed": 0,
        "errores": 0,
        "mensaje": "",
    }

    async def _correr():
        try:
            await ingest_user(db, username)
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

    asyncio.get_running_loop().create_task(_correr())
    return True
