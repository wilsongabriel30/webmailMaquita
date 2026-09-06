"""Snooze router — postpone emails to reappear later."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import (
    fetch_message_headers,
    get_imap_connection,
    uid_bulk_action,
    uid_move_message,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mail", tags=["mail-snooze"])

SNOOZE_FOLDER = "Snoozed"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SnoozeRequest(BaseModel):
    folder: str
    uid: int
    snooze_until: str  # ISO datetime


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def ensure_tables(db):
    # Tablas creadas por migrations/init_tables.sql (Fase 3)
    # snoozed_emails + índices
    pass


async def _ensure_snooze_folder(imap):
    """Create the Snoozed folder if it does not exist."""
    try:
        await imap.create(SNOOZE_FOLDER)
    except Exception:
        pass


def _parse_imap_uids(search_resp) -> list[int]:
    """Extract UID list from IMAP search response."""
    uids = []
    for line in search_resp.lines:
        s = line.decode() if isinstance(line, bytes) else line
        s = s.strip()
        if s and "completed" not in s.lower():
            uids.extend(int(x) for x in s.split() if x.isdigit())
    return uids


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/snooze", status_code=status.HTTP_201_CREATED)
async def snooze_email(
    body: SnoozeRequest, request: Request, username: str = Depends(get_current_user)
):
    """Postpone an email — move to Snoozed folder and schedule restoration."""
    db = request.app.state.db_pool
    await ensure_tables(db)
    password = await get_user_password(request, username)

    try:
        snooze_dt = datetime.fromisoformat(body.snooze_until.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid snooze_until datetime")

    if snooze_dt <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400, detail="snooze_until must be in the future"
        )

    subject = ""
    from_addr = ""
    try:
        login_user = await get_imap_login_user(request, username)
        imap = await get_imap_connection(login_user, password)
        try:
            await _ensure_snooze_folder(imap)
            await imap.select(body.folder)
            hdrs = await fetch_message_headers(imap, [body.uid])
            if hdrs:
                h = hdrs[0]
                # hdrs[0] can be dict or NormalizedMessage
                if hasattr(h, "subject"):
                    subject = (h.subject or "")[:500]
                    from_addr = (h.from_addr or "")[:255]
                elif isinstance(h, dict):
                    if h.get("raw_headers"):
                        from app.mail.parsers.mime_parser import parse_headers

                        nm = parse_headers(h["raw_headers"], uid=h.get("uid", 0))
                        subject = (nm.subject or "")[:500]
                        from_addr = (nm.from_addr or "")[:255]
                    else:
                        subject = (h.get("subject", "") or "")[:500]
                        from_addr = (h.get("from", "") or h.get("from_addr", "") or "")[
                            :255
                        ]

            moved = await uid_move_message(imap, body.folder, body.uid, SNOOZE_FOLDER)
            if not moved:
                raise HTTPException(
                    status_code=500, detail="Failed to move email to Snoozed folder"
                )
        finally:
            await imap.logout()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Snooze IMAP error: %s", e)
        raise HTTPException(status_code=500, detail=f"IMAP error: {e}")

    row = await db.fetchrow(
        """INSERT INTO snoozed_emails (owner, original_folder, original_uid, snooze_until, subject, from_addr)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING id, created_at""",
        username,
        body.folder,
        body.uid,
        snooze_dt.replace(tzinfo=None),
        subject,
        from_addr,
    )

    return {
        "id": row["id"],
        "folder": body.folder,
        "uid": body.uid,
        "snooze_until": body.snooze_until,
        "original_folder": body.folder,
        "created_at": str(row["created_at"]),
    }


@router.get("/snooze")
async def list_snoozed(request: Request, username: str = Depends(get_current_user)):
    """List all snoozed (not yet restored) emails."""
    db = request.app.state.db_pool
    await ensure_tables(db)

    rows = await db.fetch(
        """SELECT id, original_folder, original_uid, snooze_until, subject, from_addr, created_at
           FROM snoozed_emails
           WHERE owner = $1 AND restored = FALSE
           ORDER BY snooze_until ASC""",
        username,
    )
    return {
        "snoozed": [
            {
                "id": r["id"],
                "original_folder": r["original_folder"],
                "original_uid": r["original_uid"],
                "snooze_until": str(r["snooze_until"]),
                "subject": r["subject"] or "",
                "from_addr": r["from_addr"] or "",
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]
    }


@router.delete("/snooze/{snooze_id}")
async def cancel_snooze(
    snooze_id: int, request: Request, username: str = Depends(get_current_user)
):
    """Cancel a snooze and move the email back to original folder."""
    db = request.app.state.db_pool
    await ensure_tables(db)
    password = await get_user_password(request, username)

    row = await db.fetchrow(
        "SELECT id, original_folder FROM snoozed_emails WHERE id = $1 AND owner = $2 AND restored = FALSE",
        snooze_id,
        username,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Snoozed email not found")

    try:
        login_user = await get_imap_login_user(request, username)
        imap = await get_imap_connection(login_user, password)
        try:
            await imap.select(SNOOZE_FOLDER)
            search_resp = await imap.uid_search("ALL")
            if search_resp.result == "OK":
                snoozed_uids = _parse_imap_uids(search_resp)
                if snoozed_uids:
                    await uid_bulk_action(
                        imap,
                        SNOOZE_FOLDER,
                        snoozed_uids[:1],
                        "move",
                        row["original_folder"],
                    )
        finally:
            await imap.logout()
    except Exception as e:
        logger.error("Cancel snooze IMAP error: %s", e)

    await db.execute(
        "UPDATE snoozed_emails SET restored = TRUE WHERE id = $1", snooze_id
    )
    return {"ok": True, "restored_to": row["original_folder"]}


# ---------------------------------------------------------------------------
# Background task — check and restore snoozed emails
# ---------------------------------------------------------------------------


async def check_snoozed(app):
    """Background task: restore snoozed emails whose time has arrived."""
    while True:
        try:
            await asyncio.sleep(60)
            db = app.state.db_pool
            if not db:
                continue

            rows = await db.fetch("""SELECT id, owner, original_folder
                   FROM snoozed_emails
                   WHERE snooze_until <= NOW() AND restored = FALSE""")
            if not rows:
                continue

            logger.info("Snooze checker: %d emails to restore", len(rows))

            for r in rows:
                try:
                    password = await _get_password_from_redis(r["owner"])
                    if not password:
                        logger.debug(
                            "Snooze: no password cached for %s, skipping", r["owner"]
                        )
                        continue

                    imap = await get_imap_connection(r["owner"], password)
                    try:
                        await imap.select(SNOOZE_FOLDER)
                        search_resp = await imap.uid_search("ALL")
                        if search_resp.result == "OK":
                            snoozed_uids = _parse_imap_uids(search_resp)
                            if snoozed_uids:
                                await uid_bulk_action(
                                    imap,
                                    SNOOZE_FOLDER,
                                    snoozed_uids[:1],
                                    "move",
                                    r["original_folder"],
                                )
                                logger.info(
                                    "Restored snoozed email %d for %s",
                                    r["id"],
                                    r["owner"],
                                )
                    finally:
                        await imap.logout()

                    await db.execute(
                        "UPDATE snoozed_emails SET restored = TRUE WHERE id = $1",
                        r["id"],
                    )
                except Exception as e:
                    logger.error("Snooze restore error for id=%d: %s", r["id"], e)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Snooze checker error: %s", e)


async def _get_password_from_redis(username: str) -> Optional[str]:
    """Try to get cached password from Redis."""
    try:
        import redis.asyncio as aioredis

        from app.config import get_settings

        settings = get_settings()
        r = aioredis.from_url(f"redis://{settings.redis_host}:{settings.redis_port}")
        pwd = await r.get(f"user_password:{username}")
        await r.aclose()
        if pwd:
            return pwd.decode() if isinstance(pwd, bytes) else pwd
    except Exception:
        pass
    return None
