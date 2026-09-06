"""Jitsi Meet integration for video meetings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

# Use public Jitsi instance (no private Jitsi detected in infra)
import os

# Jitsi PROPIO de Maquita (soberano). Configurable vía .env si algún día cambia.
JITSI_BASE_URL = os.environ.get("JITSI_BASE_URL", "https://meet.maquita.com.ec").rstrip(
    "/"
)


def _db(request: Request):
    return request.app.state.db_pool


def _redis(request: Request):
    return request.app.state.redis


# ── Schemas ───────────────────────────────────────────────


class MeetingCreate(BaseModel):
    title: str
    start_time: Optional[datetime] = None
    attendees: list[str] = []


class MeetingOut(BaseModel):
    id: int
    room_id: str
    title: str
    creator_email: str
    meeting_url: str
    start_time: Optional[datetime] = None
    attendees: Optional[list[str]] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


class MeetingInvite(BaseModel):
    meeting_id: int
    attendees: list[str]


# ── Create meeting ────────────────────────────────────────


@router.post("/create", response_model=MeetingOut, status_code=201)
async def create_meeting(
    data: MeetingCreate,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    redis = _redis(request)

    room_id = f"maquita-{uuid.uuid4().hex[:8]}"
    meeting_url = f"{JITSI_BASE_URL}/{room_id}"

    row = await db.fetchrow(
        """INSERT INTO meetings (room_id, title, creator_email, meeting_url, start_time, attendees)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING *""",
        room_id,
        data.title,
        user,
        meeting_url,
        data.start_time,
        data.attendees,
    )

    # If start_time provided, create calendar event automatically
    if data.start_time:
        try:
            from app.calendar.service import calendar_service

            # Get or create default calendar
            await calendar_service.ensure_default_calendar(db, user)
            cals = await calendar_service.list_calendars(db, user)
            if cals:
                cal_id = cals[0]["id"] if isinstance(cals[0], dict) else cals[0].id
                from datetime import timedelta

                from app.calendar.schemas import EventCreate

                event = EventCreate(
                    title=f"Reunion: {data.title}",
                    start=data.start_time,
                    end=data.start_time + timedelta(hours=1),
                    description=f"Reunion Jitsi Meet\nURL: {meeting_url}\n\nParticipantes: {', '.join(data.attendees)}",
                    location=meeting_url,
                )
                await calendar_service.create_event(db, user, cal_id, event)
        except Exception:
            pass  # Calendar integration is best-effort

    # Send invitations if attendees specified
    if data.attendees:
        try:
            await _send_invitations(
                request, user, data.title, meeting_url, data.start_time, data.attendees
            )
        except Exception:
            pass  # Invitations are best-effort

    return dict(row)


# ── List meetings ─────────────────────────────────────────


@router.get("", response_model=list[MeetingOut])
async def list_meetings(request: Request, user: str = Depends(get_current_user)):
    db = _db(request)
    rows = await db.fetch(
        "SELECT * FROM meetings WHERE creator_email = $1 ORDER BY created_at DESC LIMIT 50",
        user,
    )
    return [dict(r) for r in rows]


# ── Send invitations ──────────────────────────────────────


@router.post("/invite")
async def invite_to_meeting(
    data: MeetingInvite,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    row = await db.fetchrow(
        "SELECT * FROM meetings WHERE id = $1 AND creator_email = $2",
        data.meeting_id,
        user,
    )
    if not row:
        raise HTTPException(404, "Reunion no encontrada")

    await _send_invitations(
        request,
        user,
        row["title"],
        row["meeting_url"],
        row["start_time"],
        data.attendees,
    )

    # Update attendees list
    existing = list(row["attendees"] or [])
    for a in data.attendees:
        if a not in existing:
            existing.append(a)
    await db.execute(
        "UPDATE meetings SET attendees = $1 WHERE id = $2",
        existing,
        data.meeting_id,
    )

    return {"status": "invitaciones_enviadas", "attendees": data.attendees}


# ── Deactivate meeting ───────────────────────────────────


@router.delete("/{meeting_id}", status_code=204)
async def deactivate_meeting(
    meeting_id: int, request: Request, user: str = Depends(get_current_user)
):
    db = _db(request)
    result = await db.execute(
        "UPDATE meetings SET is_active = false WHERE id = $1 AND creator_email = $2",
        meeting_id,
        user,
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Reunion no encontrada")


# ── Helper: send email invitations ───────────────────────


async def _send_invitations(
    request, creator, title, meeting_url, start_time, attendees
):
    """Send meeting invitation emails to attendees via SMTP."""
    redis = request.app.state.redis
    raw_pass = await redis.get(f"imap_pass:{creator}")
    if not raw_pass:
        return
    # La credencial en Redis va cifrada; leerla cruda no sirve como contraseña.
    from app.core.session import decrypt_password

    try:
        password = decrypt_password(raw_pass)
    except Exception:
        await redis.delete(f"imap_pass:{creator}")
        return

    from app.config import get_settings

    settings = get_settings()

    time_str = (
        start_time.strftime("%d/%m/%Y %H:%M") if start_time else "Sin fecha definida"
    )

    subject = f"Invitacion a reunion: {title}"
    html_body = f"""<div style="font-family:Arial,sans-serif;max-width:600px">
<h2 style="color:#1a73e8">Invitacion a Reunion</h2>
<p><strong>{creator}</strong> te invita a una reunion.</p>
<table style="margin:16px 0">
<tr><td style="padding:4px 12px 4px 0;font-weight:bold">Tema:</td><td>{title}</td></tr>
<tr><td style="padding:4px 12px 4px 0;font-weight:bold">Fecha/hora:</td><td>{time_str}</td></tr>
<tr><td style="padding:4px 12px 4px 0;font-weight:bold">Participantes:</td><td>{', '.join(attendees)}</td></tr>
</table>
<p><a href="{meeting_url}" style="display:inline-block;padding:12px 24px;background:#1a73e8;color:white;text-decoration:none;border-radius:6px;font-weight:bold">Unirse a la reunion</a></p>
<p style="color:#666;font-size:12px">URL: {meeting_url}</p>
</div>"""

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = creator
        msg["Subject"] = subject
        msg["To"] = ", ".join(attendees)
        msg.attach(
            MIMEText(
                f"Reunion: {title}\nFecha: {time_str}\nURL: {meeting_url}", "plain"
            )
        )
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(creator, password)
            smtp.sendmail(creator, attendees, msg.as_string())
    except Exception:
        pass  # Best effort
