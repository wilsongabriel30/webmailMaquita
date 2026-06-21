"""Gating por dominio del RAG (tabla rag_domains)."""


def _domain(username):
    return username.split("@")[-1].lower() if username and "@" in username else ""


async def domain_enabled(db, username):
    dom = _domain(username)
    if not dom:
        return False
    try:
        return bool(await db.fetchval("SELECT enabled FROM rag_domains WHERE domain=$1", dom))
    except Exception:
        return False


async def list_domains(db):
    try:
        return [dict(r) for r in await db.fetch("SELECT domain, enabled FROM rag_domains ORDER BY domain")]
    except Exception:
        return []
