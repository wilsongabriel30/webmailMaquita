"""Room Booking router."""
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


# ── Schemas ───────────────────────────────────────────────

class RoomOut(BaseModel):
    id: int
    name: str
    email: str | None = None
    capacity: int
    location: str | None = None
    amenities: list[str] = []
    is_active: bool = True

class RoomCreate(BaseModel):
    name: str
    email: str | None = None
    capacity: int = 10
    location: str | None = None
    amenities: list[str] = Field(default_factory=list)

class RoomUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    capacity: int | None = None
    location: str | None = None
    amenities: list[str] | None = None
    is_active: bool | None = None

class BookingOut(BaseModel):
    id: int
    room_id: int
    room_name: str | None = None
    event_id: int | None = None
    user_email: str
    title: str
    start_time: datetime
    end_time: datetime
    status: str

class BookingCreate(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    event_id: int | None = None

class SlotInfo(BaseModel):
    start: str
    end: str
    available: bool
    booking: BookingOut | None = None

class AvailabilityResponse(BaseModel):
    room_id: int
    date: str
    slots: list[SlotInfo]


def _db(request: Request):
    return request.app.state.db_pool


# ── Room CRUD ─────────────────────────────────────────────

@router.get("", response_model=list[RoomOut])
async def list_rooms(
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    rows = await db.fetch(
        "SELECT * FROM meeting_rooms WHERE is_active = true ORDER BY name"
    )
    return [RoomOut(**dict(r)) for r in rows]


@router.get("/{room_id}", response_model=RoomOut)
async def get_room(
    room_id: int,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    row = await db.fetchrow("SELECT * FROM meeting_rooms WHERE id = $1", room_id)
    if not row:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    return RoomOut(**dict(row))


@router.post("", response_model=RoomOut, status_code=201)
async def create_room(
    data: RoomCreate,
    request: Request,
    admin: str = Depends(require_admin),
):
    db = _db(request)
    row = await db.fetchrow(
        """INSERT INTO meeting_rooms (name, email, capacity, location, amenities)
           VALUES ($1, $2, $3, $4, $5) RETURNING *""",
        data.name, data.email, data.capacity, data.location, data.amenities,
    )
    return RoomOut(**dict(row))


@router.put("/{room_id}", response_model=RoomOut)
async def update_room(
    room_id: int,
    data: RoomUpdate,
    request: Request,
    admin: str = Depends(require_admin),
):
    db = _db(request)
    existing = await db.fetchrow("SELECT * FROM meeting_rooms WHERE id = $1", room_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Sala no encontrada")

    updates = data.model_dump(exclude_none=True)
    if not updates:
        return RoomOut(**dict(existing))

    set_clauses = []
    params = [room_id]  # $1 = room_id
    idx = 2
    for key, val in updates.items():
        set_clauses.append(f"{key} = ${idx}")
        params.append(val)
        idx += 1

    row = await db.fetchrow(
        f"UPDATE meeting_rooms SET {', '.join(set_clauses)} WHERE id = $1 RETURNING *",
        *params,
    )
    return RoomOut(**dict(row))


@router.delete("/{room_id}", status_code=204)
async def delete_room(
    room_id: int,
    request: Request,
    admin: str = Depends(require_admin),
):
    db = _db(request)
    result = await db.execute("DELETE FROM meeting_rooms WHERE id = $1", room_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Sala no encontrada")


# ── Availability ──────────────────────────────────────────

@router.get("/{room_id}/availability", response_model=AvailabilityResponse)
async def room_availability(
    room_id: int,
    request: Request,
    date_str: str = Query(..., alias="date", description="YYYY-MM-DD"),
    user: str = Depends(get_current_user),
):
    db = _db(request)
    room = await db.fetchrow("SELECT * FROM meeting_rooms WHERE id = $1", room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Sala no encontrada")

    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha invalido. Use YYYY-MM-DD")

    day_start = datetime.combine(target_date, datetime.min.time().replace(hour=8))
    day_end = datetime.combine(target_date, datetime.min.time().replace(hour=18))

    bookings = await db.fetch(
        """SELECT rb.*, mr.name AS room_name
           FROM room_bookings rb
           JOIN meeting_rooms mr ON mr.id = rb.room_id
           WHERE rb.room_id = $1
             AND rb.start_time < $3
             AND rb.end_time > $2
             AND rb.status = 'confirmed'
           ORDER BY rb.start_time""",
        room_id, day_start, day_end,
    )

    slots = []
    current = day_start
    while current < day_end:
        slot_end = current + timedelta(minutes=30)
        booking_match = None
        for b in bookings:
            if b["start_time"] < slot_end and b["end_time"] > current:
                booking_match = BookingOut(
                    id=b["id"],
                    room_id=b["room_id"],
                    room_name=b["room_name"],
                    event_id=b["event_id"],
                    user_email=b["user_email"],
                    title=b["title"],
                    start_time=b["start_time"],
                    end_time=b["end_time"],
                    status=b["status"],
                )
                break
        slots.append(SlotInfo(
            start=current.strftime("%H:%M"),
            end=slot_end.strftime("%H:%M"),
            available=booking_match is None,
            booking=booking_match,
        ))
        current = slot_end

    return AvailabilityResponse(room_id=room_id, date=date_str, slots=slots)


# ── Bookings ──────────────────────────────────────────────

@router.post("/{room_id}/book", response_model=BookingOut, status_code=201)
async def book_room(
    room_id: int,
    data: BookingCreate,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    room = await db.fetchrow("SELECT * FROM meeting_rooms WHERE id = $1 AND is_active = true", room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Sala no encontrada o inactiva")

    if data.end_time <= data.start_time:
        raise HTTPException(status_code=400, detail="La hora de fin debe ser posterior a la de inicio")

    # Verificar conflictos
    conflict = await db.fetchval(
        """SELECT COUNT(*) FROM room_bookings
           WHERE room_id = $1
             AND status = 'confirmed'
             AND start_time < $2
             AND end_time > $3""",
        room_id, data.start_time, data.end_time,
    )
    if conflict > 0:
        raise HTTPException(status_code=409, detail="La sala ya esta reservada en ese horario")

    row = await db.fetchrow(
        """INSERT INTO room_bookings (room_id, event_id, user_email, title, start_time, end_time)
           VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
        room_id, data.event_id, user, data.title, data.start_time, data.end_time,
    )
    return BookingOut(
        id=row["id"],
        room_id=row["room_id"],
        room_name=room["name"],
        event_id=row["event_id"],
        user_email=row["user_email"],
        title=row["title"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        status=row["status"],
    )


@router.delete("/bookings/{booking_id}", status_code=204)
async def cancel_booking(
    booking_id: int,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    row = await db.fetchrow(
        "SELECT * FROM room_bookings WHERE id = $1", booking_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    if row["user_email"] != user:
        # Verificar si es admin
        admin_row = await db.fetchrow(
            "SELECT 1 FROM admin WHERE username = $1 AND active = true", user
        )
        if not admin_row:
            raise HTTPException(status_code=403, detail="Solo el creador o un admin puede cancelar")

    await db.execute(
        "UPDATE room_bookings SET status = 'cancelled' WHERE id = $1", booking_id
    )


@router.get("/bookings/mine", response_model=list[BookingOut])
async def my_bookings(
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    rows = await db.fetch(
        """SELECT rb.*, mr.name AS room_name
           FROM room_bookings rb
           JOIN meeting_rooms mr ON mr.id = rb.room_id
           WHERE rb.user_email = $1
             AND rb.status = 'confirmed'
             AND rb.end_time > NOW()
           ORDER BY rb.start_time""",
        user,
    )
    return [
        BookingOut(
            id=r["id"],
            room_id=r["room_id"],
            room_name=r["room_name"],
            event_id=r["event_id"],
            user_email=r["user_email"],
            title=r["title"],
            start_time=r["start_time"],
            end_time=r["end_time"],
            status=r["status"],
        )
        for r in rows
    ]
