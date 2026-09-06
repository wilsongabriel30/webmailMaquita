"""Ingesta incremental de la bandeja de un usuario al índice RAG."""

import os

from app.config import get_settings
from app.rag import config as rag_config
from app.rag import store
from app.rag.embeddings import embed


async def ingest_user(db, username, limit=None):
    # Tope configurable via RAG_INGEST_LIMIT (antes 200 fijo: el asistente
    # solo veia los ultimos 200 correos). Default alto para cubrir la bandeja.
    if limit is None:
        limit = int(os.getenv("RAG_INGEST_LIMIT", "3000"))
    if not await rag_config.domain_enabled(db, username):
        return {"username": username, "skipped": "dominio no habilitado", "indexed": 0}
    await store.ensure_schema(db)
    s = get_settings()
    from app.mail.clients.imap_client import get_imap_connection
    from app.mail.services.message_service import list_messages

    try:
        imap = await get_imap_connection(f"{username}*admin", s.master_password)
    except Exception as e:
        return {"username": username, "error": f"IMAP: {e}", "indexed": 0}
    try:
        res = await list_messages(imap, "INBOX", 1, limit, "")
        msgs = (res or {}).get("messages", []) if res else []
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
    have = await store.existing_uids(db, username)
    indexed = 0
    for m in msgs:
        uid = str(m.get("uid", ""))
        if not uid or uid in have:
            continue
        content = f"De: {m.get('from','')} | Asunto: {m.get('subject','')} | {m.get('snippet','')}"
        emb = await embed(content)
        if not emb:
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
    return {
        "username": username,
        "indexed": indexed,
        "total": await store.count(db, username),
    }
