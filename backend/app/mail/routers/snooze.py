"""Snooze router — postpone emails to reappear later."""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import (
    fetch_message_headers,
    get_imap_connection,
    uid_move_message_detallado,
)
from app.mail.services import pospuestos

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

    if snooze_dt.tzinfo is None:
        snooze_dt = snooze_dt.replace(tzinfo=timezone.utc)
    if snooze_dt <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400, detail="snooze_until must be in the future"
        )

    subject = ""
    from_addr = ""
    snoozed_uid = None
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

            # Se anota el UID que el correo recibe dentro de Pospuestos: es lo que permite devolver
            # después ESE correo y no «el primero» de la carpeta.
            moved, mapa = await uid_move_message_detallado(
                imap, body.folder, body.uid, SNOOZE_FOLDER
            )
            snoozed_uid = (mapa or {}).get(body.uid)
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
        """INSERT INTO snoozed_emails
               (owner, original_folder, original_uid, snooze_until, subject, from_addr, snoozed_uid)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           RETURNING id, created_at""",
        username,
        body.folder,
        body.uid,
        snooze_dt.astimezone(timezone.utc).replace(tzinfo=None),
        subject,
        from_addr,
        snoozed_uid,
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
    await _devolver_los_mios(request, db, username)

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
        """SELECT id, owner, original_folder, snoozed_uid, subject, from_addr
             FROM snoozed_emails WHERE id = $1 AND owner = $2 AND restored = FALSE""",
        snooze_id,
        username,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Snoozed email not found")

    try:
        login_user = await get_imap_login_user(request, username)
        imap = await get_imap_connection(login_user, password)
        try:
            resultado = await pospuestos.devolver(imap, row)
        finally:
            await imap.logout()
    except Exception as e:
        logger.error("Cancel snooze IMAP error: %s", e)
        raise HTTPException(
            status_code=502, detail="No se pudo devolver el correo a su carpeta."
        )
    if resultado not in (pospuestos.DEVUELTO, pospuestos.YA_NO_ESTABA):
        # Antes se marcaba como devuelto aunque no se hubiera movido nada.
        raise HTTPException(
            status_code=409,
            detail="No se pudo identificar el correo en Pospuestos. Muévalo a mano desde esa carpeta.",
        )

    await db.execute(
        "UPDATE snoozed_emails SET restored = TRUE WHERE id = $1", snooze_id
    )
    return {"ok": True, "restored_to": row["original_folder"]}


async def _devolver_los_mios(request: Request, db, username: str) -> None:
    """Devuelve lo vencido de quien consulta, con su propia sesión.

    El restaurador en segundo plano necesita el usuario maestro; en una instalación que no lo tenga,
    los pospuestos vuelven al menos cuando la persona abre el correo.
    """
    try:
        if not await db.fetchval(
            """SELECT 1 FROM snoozed_emails
                WHERE owner = $1 AND restored = FALSE
                  AND snooze_until <= (NOW() AT TIME ZONE 'UTC') LIMIT 1""",
            username,
        ):
            return
        password = await get_user_password(request, username)
        login_user = await get_imap_login_user(request, username)
        imap = await get_imap_connection(login_user, password)
        try:
            await pospuestos.restaurar_vencidos(db, owner=username, imap=imap)
        finally:
            await imap.logout()
    except Exception as e:
        logger.warning(
            "Pospuestos de %s: no se pudieron devolver al listar: %s", username, e
        )


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

            # Una sola revisión por minuto en todo el clúster: dos workers moviendo a la
            # vez el mismo pospuesto lo devolverían dos veces (ver app/escala/bloqueo.py).
            from app.escala.bloqueo import una_vez_por_intervalo

            async with una_vez_por_intervalo(
                app.state.redis, "snooze:revision", 55
            ) as turno:
                if turno.obtenido:
                    await _restaurar_vencidos(db)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Snooze checker error: %s", e)


async def _restaurar_vencidos(db):
    """Una vuelta del restaurador de pospuestos (ver app/mail/services/pospuestos.py)."""
    resumen = await pospuestos.restaurar_vencidos(db)
    if resumen.get(pospuestos.DEVUELTO):
        logger.info(
            "Pospuestos devueltos a su carpeta: %d", resumen[pospuestos.DEVUELTO]
        )
