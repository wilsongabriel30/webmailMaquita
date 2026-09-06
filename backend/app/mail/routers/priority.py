"""
Bandeja priorizada IA — Maquita Webmail
========================================
Clasifica correos usando VM 170 (LLM) y cachea resultados en PostgreSQL.
Endpoint: GET /api/mail/priority — devuelve correos separados por prioridad.
"""

import logging
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.core.session import get_imap_login_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mail", tags=["priority"])

from app.config import get_settings as _gs

IA_CLASSIFY_URL = f"{_gs().ollama_url}/api/v1/email-assistant/classify/batch"
IA_TIMEOUT = 60.0
IA_HEADERS = {"X-API-Key": get_settings().ia_api_key}  # Securizado Fase 3


async def ensure_tables(db):
    # Tabla creada por migrations/init_tables.sql (Fase 3)
    # priority_cache + índice
    pass


def _is_maquita_domain(from_addr: str) -> bool:
    """Verifica si el remitente es de un dominio *maquita*."""
    import re
    email_match = re.search(r"<([^>]+)>", from_addr)
    email = email_match.group(1).lower() if email_match else from_addr.strip().lower()
    domain = email.split("@")[-1] if "@" in email else ""
    return "maquita" in domain


@router.get("/priority")
async def get_priority_inbox(
    request: Request,
    folder: str = "INBOX",
    limit: int = 50,
    user: str = Depends(get_current_user),
):
    """
    Devuelve correos del folder separados por prioridad.
    Clasifica automáticamente los que no tienen cache.
    """
    db = request.app.state.db_pool
    await ensure_tables(db)

    # 1) Obtener lista de mensajes del folder (los últimos N)
    # IMPORTANTE: Las contraseñas en Redis están cifradas con Fernet.
    # NUNCA leer directo con redis.get("imap_pass:...") — eso devuelve el token cifrado.
    # SIEMPRE usar get_user_password() que descifra automáticamente.
    # Bug original (2026-04-13): se pasaba el token cifrado a IMAP → "login failed".
    from app.core.session import get_user_password as _get_pass
    from app.mail.clients.imap_client import get_imap_connection
    from app.mail.services.message_service import list_messages
    password = await _get_pass(request, user)

    login_user = await get_imap_login_user(request, user)
    imap = await get_imap_connection(login_user, password)
    try:
        result = await list_messages(imap, folder, page=1, per_page=limit)
        messages = result.get("messages", [])
    finally:
        try:
            await imap.logout()
        except Exception:
            pass

    if not messages:
        return {"high": [], "normal": [], "low": []}

    # 2) Buscar clasificaciones en cache
    uids = [m["uid"] for m in messages]
    placeholders = ", ".join(f"${i+3}" for i in range(len(uids)))
    cached = await db.fetch(
        f"SELECT message_uid, priority, category, confidence, reason FROM priority_cache "
        f"WHERE owner = $1 AND folder = $2 AND message_uid IN ({placeholders})",
        user, folder, *uids
    )
    cache_map = {r["message_uid"]: dict(r) for r in cached}

    # 3) Clasificar los que no tienen cache (en batch)
    uncached = [m for m in messages if m["uid"] not in cache_map]
    if uncached:
        # Pre-clasificar correos de dominios *maquita* como prioritarios
        still_uncached = []
        for m in uncached:
            if _is_maquita_domain(m.get("from", "")):
                await db.execute(
                    """INSERT INTO priority_cache (owner, folder, message_uid, priority, category, confidence, reason)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)
                       ON CONFLICT (owner, folder, message_uid) DO NOTHING""",
                    user, folder, m["uid"], "high", "domain_rule", 1.0, "Dominio Maquita - clasificado automaticamente"
                )
                # Solo insertar si no fue manual (DO NOTHING respeta manual)
                if m["uid"] not in cache_map:
                    cache_map[m["uid"]] = {
                        "message_uid": m["uid"],
                        "priority": "high",
                        "category": "domain_rule",
                        "confidence": 1.0,
                        "reason": "Dominio Maquita - clasificado automáticamente",
                    }
            else:
                still_uncached.append(m)
        uncached = still_uncached

        try:
            batch_emails = []
            for m in uncached[:10]:  # Max 10 por batch
                batch_emails.append({
                    "subject": m.get("subject", ""),
                    "from_addr": m.get("from", ""),
                    "snippet": m.get("snippet", m.get("text_body", ""))[:200],
                    "to_addr": user,
                })

            async with httpx.AsyncClient(timeout=IA_TIMEOUT) as client:
                resp = await client.post(IA_CLASSIFY_URL, json={"emails": batch_emails}, headers=IA_HEADERS)
                resp.raise_for_status()
                classify_data = resp.json()

            results = classify_data.get("results", [])
            for i, m in enumerate(uncached[:10]):
                if i < len(results):
                    r = results[i]
                    priority = r.get("priority", "normal")
                    category = r.get("category", "other")
                    confidence = r.get("confidence", 0.5)
                    reason = r.get("reason", "")
                else:
                    priority, category, confidence, reason = "normal", "other", 0.3, ""

                # Guardar en cache
                await db.execute(
                    """INSERT INTO priority_cache (owner, folder, message_uid, priority, category, confidence, reason)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)
                       ON CONFLICT (owner, folder, message_uid) DO UPDATE
                       SET priority = $4, category = $5, confidence = $6, reason = $7, classified_at = now()""",
                    user, folder, m["uid"], priority, category, confidence, reason
                )
                cache_map[m["uid"]] = {
                    "message_uid": m["uid"],
                    "priority": priority,
                    "category": category,
                    "confidence": confidence,
                    "reason": reason,
                }

        except Exception as e:
            logger.warning(f"IA classify failed: {e}")
            # Si falla IA, todo queda como "normal"
            for m in uncached:
                if m["uid"] not in cache_map:
                    cache_map[m["uid"]] = {
                        "message_uid": m["uid"],
                        "priority": "normal",
                        "category": "other",
                        "confidence": 0.0,
                        "reason": "clasificación no disponible",
                    }

    # 4) Separar por prioridad
    high, normal, low = [], [], []
    for m in messages:
        cached_info = cache_map.get(m["uid"], {})
        m["priority"] = cached_info.get("priority", "normal")
        m["category"] = cached_info.get("category", "other")
        m["priority_reason"] = cached_info.get("reason", "")

        if m["priority"] == "high":
            high.append(m)
        elif m["priority"] == "low":
            low.append(m)
        else:
            normal.append(m)

    return {"high": high, "normal": normal, "low": low}


@router.post("/priority/reclassify")
async def reclassify_message(
    request: Request,
    user: str = Depends(get_current_user),
):
    """Permite al usuario reclasificar manualmente un correo."""
    body = await request.json()
    folder = body.get("folder", "INBOX")
    uid = body.get("uid")
    new_priority = body.get("priority", "normal")

    if not uid:
        raise HTTPException(status_code=400, detail="uid requerido")
    if new_priority not in ("high", "normal", "low"):
        raise HTTPException(status_code=400, detail="priority debe ser high, normal o low")

    db = request.app.state.db_pool
    await ensure_tables(db)

    await db.execute(
        """INSERT INTO priority_cache (owner, folder, message_uid, priority, category, confidence, reason)
           VALUES ($1, $2, $3, $4, 'manual', 1.0, 'Clasificado manualmente por el usuario')
           ON CONFLICT (owner, folder, message_uid) DO UPDATE
           SET priority = $4, category = 'manual', confidence = 1.0,
               reason = 'Clasificado manualmente por el usuario', classified_at = now()""",
        user, folder, uid, new_priority
    )

    return {"ok": True, "uid": uid, "priority": new_priority}


@router.delete("/priority/cache")
async def clear_priority_cache(
    request: Request,
    folder: str = "INBOX",
    user: str = Depends(get_current_user),
):
    """Limpia el cache de prioridades para forzar reclasificación."""
    db = request.app.state.db_pool
    await ensure_tables(db)
    result = await db.execute(
        "DELETE FROM priority_cache WHERE owner = $1 AND folder = $2",
        user, folder
    )
    return {"ok": True, "deleted": result.split()[-1] if result else "0"}
