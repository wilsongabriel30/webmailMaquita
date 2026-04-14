"""FastAPI router for Calendar API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

from app.auth.dependencies import get_current_user
from app.calendar.schemas import (
    CalendarCreate,
    CalendarOut,
    CalendarShareCreate,
    CalendarUpdate,
    EventCreate,
    EventInvitationResponse,
    EventMove,
    EventOut,
    EventUpdate,
    FreeBusyResponse,
)
from app.calendar.service import calendar_service

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _db(request: Request):
    return request.app.state.db_pool


# ── Calendars ─────────────────────────────────────────────


@router.get("/calendars", response_model=list[CalendarOut])
async def list_calendars(
    request: Request, user: str = Depends(get_current_user)
):
    db = _db(request)
    # Ensure at least a default calendar exists
    await calendar_service.ensure_default_calendar(db, user)
    return await calendar_service.list_calendars(db, user)


@router.post("/calendars", response_model=CalendarOut, status_code=201)
async def create_calendar(
    data: CalendarCreate,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    return await calendar_service.create_calendar(db, user, data)


@router.patch("/calendars/{calendar_id}", response_model=CalendarOut)
async def update_calendar(
    calendar_id: uuid.UUID,
    data: CalendarUpdate,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    try:
        return await calendar_service.update_calendar(db, user, calendar_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/calendars/{calendar_id}", status_code=204)
async def delete_calendar(
    calendar_id: uuid.UUID,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    try:
        await calendar_service.delete_calendar(db, user, calendar_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Events ────────────────────────────────────────────────


@router.get("/events", response_model=list[EventOut])
async def list_events(
    request: Request,
    start: datetime = Query(..., description="Range start (ISO 8601)"),
    end: datetime = Query(..., description="Range end (ISO 8601)"),
    calendar_id: Optional[uuid.UUID] = Query(None),
    user: str = Depends(get_current_user),
):
    db = _db(request)
    return await calendar_service.list_events(db, user, start, end, calendar_id)


@router.get("/events/{event_id}", response_model=EventOut)
async def get_event(
    event_id: uuid.UUID,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    try:
        return await calendar_service.get_event(db, user, event_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/events", response_model=EventOut, status_code=201)
async def create_event(
    data: EventCreate,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    try:
        return await calendar_service.create_event(db, user, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/events/{event_id}", response_model=EventOut)
async def update_event(
    event_id: uuid.UUID,
    data: EventUpdate,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    try:
        return await calendar_service.update_event(db, user, event_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/events/{event_id}/move", response_model=EventOut)
async def move_event(
    event_id: uuid.UUID,
    data: EventMove,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    try:
        return await calendar_service.move_event(db, user, event_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(
    event_id: uuid.UUID,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    try:
        await calendar_service.delete_event(db, user, event_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/export/{calendar_id}")
async def export_calendar(
    calendar_id: uuid.UUID,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    try:
        ical_str = await calendar_service.export_calendar(db, user, calendar_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return PlainTextResponse(
        content=ical_str,
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=calendar.ics"},
    )


# ── Free/Busy ─────────────────────────────────────────────


@router.get("/freebusy", response_model=FreeBusyResponse)
async def freebusy(
    request: Request,
    user_email: str = Query(..., alias="user", description="Email del usuario a consultar"),
    start: datetime = Query(..., description="Inicio del rango (ISO 8601)"),
    end: datetime = Query(..., description="Fin del rango (ISO 8601)"),
    _current_user: str = Depends(get_current_user),
):
    """Consultar disponibilidad (free/busy) de otro usuario."""
    db = _db(request)
    slots = await calendar_service.freebusy(db, user_email, start, end)
    return FreeBusyResponse(user=user_email, slots=slots)


# ── Calendar Sharing ──────────────────────────────────────

@router.post("/calendars/{calendar_id}/share", status_code=201)
async def share_calendar(
    calendar_id: uuid.UUID,
    data: CalendarShareCreate,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Compartir un calendario con otro usuario."""
    db = _db(request)
    try:
        result = await calendar_service.share_calendar(db, user, calendar_id, data.shared_with, data.permission)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/calendars/{calendar_id}/shares")
async def list_calendar_shares(
    calendar_id: uuid.UUID,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Listar con quiénes está compartido un calendario mío."""
    db = _db(request)
    try:
        return await calendar_service.list_shares_of_calendar(db, user, calendar_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/calendars/{calendar_id}/share/{shared_with}", status_code=204)
async def revoke_calendar_share(
    calendar_id: uuid.UUID,
    shared_with: str,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Revocar acceso compartido a un calendario."""
    db = _db(request)
    try:
        await calendar_service.revoke_share(db, user, calendar_id, shared_with)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/shared")
async def list_shared_with_me(
    request: Request,
    user: str = Depends(get_current_user),
):
    """Listar calendarios compartidos conmigo."""
    db = _db(request)
    return await calendar_service.list_shared_with_me(db, user)


@router.get("/shared/events", response_model=list[EventOut])
async def list_shared_events(
    request: Request,
    start: datetime = Query(..., description="Inicio del rango (ISO 8601)"),
    end: datetime = Query(..., description="Fin del rango (ISO 8601)"),
    user: str = Depends(get_current_user),
):
    """Listar eventos de calendarios compartidos conmigo."""
    db = _db(request)
    return await calendar_service.list_events_shared(db, user, start, end)


# ── Event Invitations ─────────────────────────────────────

@router.post("/events/{event_id}/invite", status_code=200)
async def send_event_invitations(
    event_id: uuid.UUID,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Enviar emails de invitación a todos los asistentes de un evento."""
    db = _db(request)
    from app.config import get_settings
    _s = get_settings()
    smtp_config = {
        "host": getattr(_s, "smtp_host", "127.0.0.1"),
        "port": int(getattr(_s, "smtp_port", 25)),
    }
    try:
        sent = await calendar_service.send_invitations(db, user, event_id, smtp_config)
        return {"sent": sent}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/events/{event_id}/respond", status_code=200)
async def respond_event_invitation(
    event_id: uuid.UUID,
    data: EventInvitationResponse,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Aceptar, rechazar o marcar como tentativa una invitación a evento."""
    db = _db(request)
    try:
        return await calendar_service.respond_invitation(db, user, event_id, data.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Scheduling Assistant ─────────────────────────────────
@router.get("/scheduling-assistant")
async def scheduling_assistant(
    attendees: str = Query(..., description="Comma-separated emails"),
    date: str = Query(..., description="YYYY-MM-DD"),
    duration: int = Query(30, description="Minutes"),
    request: Request = None,
    user: str = Depends(get_current_user),
):
    """Find common free slots for multiple attendees on a given date."""
    db = request.app.state.db_pool
    emails = [e.strip() for e in attendees.split(",") if e.strip()]
    if not emails:
        raise HTTPException(400, "Se requiere al menos un asistente")
    
    from datetime import datetime as dt, timedelta
    target = dt.strptime(date, "%Y-%m-%d").date()
    start_str = f"{date}T00:00:00"
    end_str = f"{date}T23:59:59"
    
    # Collect busy times per attendee
    all_busy: list[tuple[dt, dt]] = []
    for email in emails:
        # Query events for this user on this date
        rows = await db.fetch(
            """SELECT start_time, end_time FROM calendar_events ce
               JOIN calendars c ON ce.calendar_id = c.id
               WHERE c.owner = $1 AND ce.start_time::date = $2
               ORDER BY ce.start_time""",
            email, target
        )
        for row in rows:
            s = row["start_time"] if isinstance(row["start_time"], dt) else dt.fromisoformat(str(row["start_time"]))
            e = row["end_time"] if isinstance(row["end_time"], dt) else dt.fromisoformat(str(row["end_time"]))
            all_busy.append((s, e))
    
    # Merge overlapping busy intervals
    all_busy.sort(key=lambda x: x[0])
    merged: list[tuple[dt, dt]] = []
    for s, e in all_busy:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    
    # Find free slots in work hours (8:00-18:00)
    work_start = dt.combine(target, dt.min.time().replace(hour=8))
    work_end = dt.combine(target, dt.min.time().replace(hour=18))
    dur = timedelta(minutes=duration)
    
    free_slots = []
    cursor = work_start
    for bs, be in merged:
        while cursor + dur <= bs and cursor + dur <= work_end:
            free_slots.append({"start": cursor.isoformat(), "end": (cursor + dur).isoformat()})
            cursor += timedelta(minutes=15)
            if len(free_slots) >= 20:
                break
        cursor = max(cursor, be)
        if len(free_slots) >= 20:
            break
    # After last busy period
    while cursor + dur <= work_end and len(free_slots) < 20:
        free_slots.append({"start": cursor.isoformat(), "end": (cursor + dur).isoformat()})
        cursor += timedelta(minutes=15)
    
    return {
        "date": date,
        "attendees": emails,
        "duration_minutes": duration,
        "busy_periods": [{"start": s.isoformat(), "end": e.isoformat()} for s, e in merged],
        "free_slots": free_slots,
    }
