"""CalendarService — dual-write to Radicale + PostgreSQL."""

from __future__ import annotations

import json
import re

from app.branding.service import app_name_cacheado, org_name_cacheado
from app.core.sanitize import sanitize_html, strip_html


def _merge_attendees(data):
    """Merge required and optional attendees into a single list with roles."""
    attendees = []
    req = getattr(data, "attendees", []) or []
    opt = getattr(data, "optional_attendees", []) or []
    for a in req:
        if isinstance(a, str):
            attendees.append({"email": a, "role": "REQ-PARTICIPANT"})
        elif isinstance(a, dict):
            a.setdefault("role", "REQ-PARTICIPANT")
            attendees.append(a)
    for a in opt:
        if isinstance(a, str):
            attendees.append({"email": a, "role": "OPT-PARTICIPANT"})
        elif isinstance(a, dict):
            a["role"] = "OPT-PARTICIPANT"
            attendees.append(a)
    return attendees


import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

import asyncpg
from dateutil.rrule import rrulestr

from app.calendar.ical_utils import build_vcalendar, generate_uid
from app.calendar.radicale_client import radicale_client
from app.calendar.schemas import (
    CalendarCreate,
    CalendarOut,
    CalendarUpdate,
    EventCreate,
    EventMove,
    EventOut,
    EventUpdate,
)

logger = logging.getLogger("calendar.service")


def _user_prefix(user: str) -> str:
    """Radicale collection path prefix for a user."""
    return user.split("@")[0] if "@" in user else user


def _row_to_calendar(row: asyncpg.Record) -> CalendarOut:
    return CalendarOut(
        id=row["id"],
        name=row["name"],
        color=row["color"],
        description=row["description"] or "",
        timezone=row["timezone"],
        is_default=row["is_default"],
    )


def _reunion_id_de(descripcion) -> Optional[int]:
    """T-30: número de la marca X-MAQUITA-REUNION: <id> en la descripción (o None)."""
    m = re.search(r"X-MAQUITA-REUNION:\s*(\d+)", descripcion or "")
    return int(m.group(1)) if m else None


def _meet_url_de(descripcion, location) -> str:
    m = re.search(r"Meet Maquita:\s*(\S+)", descripcion or "")
    if m:
        return m.group(1)
    return location if re.match(r"https?://meet\.", location or "") else ""


def _row_to_event(row: asyncpg.Record) -> EventOut:
    reminders = row["reminders"]
    if isinstance(reminders, str):
        reminders = json.loads(reminders)
    attendees = row["attendees"]
    if isinstance(attendees, str):
        attendees = json.loads(attendees)
    return EventOut(
        id=row["id"],
        calendar_id=row["calendar_id"],
        uid=row["uid"],
        summary=row["summary"],
        description=row["description"] or "",
        location=row["location"] or "",
        dtstart=row["dtstart"],
        dtend=row["dtend"],
        all_day=row["all_day"],
        rrule=row["rrule"] or "",
        status=row["status"] or "CONFIRMED",
        color=row["color"],
        calendar_name=row["calendar_name"],
        timezone=row["timezone"] or "America/Guayaquil",
        reminders=reminders if reminders else [],
        attendees=attendees if attendees else [],
        reunion_id=_reunion_id_de(row["description"]),
        meet_url=_meet_url_de(row["description"], row["location"]),
    )


def _expand_recurrence(
    event: EventOut, range_start: datetime, range_end: datetime
) -> list[EventOut]:
    """Expand a recurrent event into individual occurrences within [range_start, range_end]."""
    try:
        duration = event.dtend - event.dtstart
        tzinfo = event.dtstart.tzinfo
        if tzinfo is not None:
            if range_start.tzinfo is None:
                range_start = range_start.replace(tzinfo=tzinfo)
            if range_end.tzinfo is None:
                range_end = range_end.replace(tzinfo=tzinfo)
        dtstart_str = event.dtstart.replace(tzinfo=None).strftime("%Y%m%dT%H%M%S")
        rrule_text = f"DTSTART:{dtstart_str}\n{event.rrule}"
        rule = rrulestr(rrule_text, ignoretz=True)

        occurrences: list[EventOut] = []
        for i, occ_start in enumerate(rule):
            if i > 500:
                break
            if tzinfo is not None:
                occ_start = occ_start.replace(tzinfo=tzinfo)
            occ_end = occ_start + duration
            if occ_end <= range_start:
                continue
            if occ_start >= range_end:
                break
            occurrences.append(
                EventOut(
                    id=event.id,
                    calendar_id=event.calendar_id,
                    uid=event.uid,
                    summary=event.summary,
                    description=event.description,
                    location=event.location,
                    dtstart=occ_start,
                    dtend=occ_end,
                    all_day=event.all_day,
                    rrule=event.rrule,
                    status=event.status,
                    color=event.color,
                    calendar_name=event.calendar_name,
                    timezone=event.timezone,
                    reminders=event.reminders,
                    attendees=event.attendees,
                )
            )
        return occurrences if occurrences else [event]
    except Exception as exc:
        logger.warning("Cannot expand rrule for event %s: %s", event.uid, exc)
        return [event]


class CalendarService:
    """Dual-write calendar service (PostgreSQL + Radicale)."""

    # Ã¢ÂÂÃ¢ÂÂ Calendars Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

    async def ensure_default_calendar(self, db: asyncpg.Pool, user: str) -> CalendarOut:
        """Create a default calendar for user if none exists. Returns it."""
        row = await db.fetchrow(
            "SELECT * FROM calendars WHERE owner_email = $1 AND is_default = true",
            user,
        )
        if row:
            return _row_to_calendar(row)

        # Check if user has any calendars at all
        count = await db.fetchval(
            "SELECT count(*) FROM calendars WHERE owner_email = $1", user
        )
        is_default = count == 0

        prefix = _user_prefix(user)
        cal_path = f"{prefix}/default"

        # Create in Radicale
        await radicale_client.ensure_calendar(user, cal_path, "Calendario", "#0078d4")

        # Create in PostgreSQL
        row = await db.fetchrow(
            """INSERT INTO calendars (owner_email, name, color, description, timezone, radicale_path, is_default)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               RETURNING *""",
            user,
            "Calendario",
            "#0078d4",
            "",
            "America/Guayaquil",
            cal_path,
            is_default,
        )
        logger.info("Default calendar created for %s", user)
        return _row_to_calendar(row)

    async def create_calendar(
        self, db: asyncpg.Pool, user: str, data: CalendarCreate
    ) -> CalendarOut:
        prefix = _user_prefix(user)
        slug = data.name.lower().replace(" ", "-")[:30]
        cal_path = f"{prefix}/{slug}-{uuid.uuid4().hex[:8]}"

        # Create in Radicale
        await radicale_client.ensure_calendar(user, cal_path, data.name, data.color)

        # Check if this should be default (first calendar)
        count = await db.fetchval(
            "SELECT count(*) FROM calendars WHERE owner_email = $1", user
        )

        row = await db.fetchrow(
            """INSERT INTO calendars (owner_email, name, color, description, timezone, radicale_path, is_default)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               RETURNING *""",
            user,
            data.name,
            data.color,
            data.description,
            data.timezone,
            cal_path,
            count == 0,
        )
        return _row_to_calendar(row)

    async def list_calendars(self, db: asyncpg.Pool, user: str) -> list[CalendarOut]:
        rows = await db.fetch(
            "SELECT * FROM calendars WHERE owner_email = $1 ORDER BY is_default DESC, name",
            user,
        )
        return [_row_to_calendar(r) for r in rows]

    async def update_calendar(
        self, db: asyncpg.Pool, user: str, calendar_id: uuid.UUID, data: CalendarUpdate
    ) -> CalendarOut:
        row = await db.fetchrow(
            "SELECT * FROM calendars WHERE id = $1 AND owner_email = $2",
            calendar_id,
            user,
        )
        if not row:
            raise ValueError("Calendar not found")

        updates = data.model_dump(exclude_none=True)
        if not updates:
            return _row_to_calendar(row)

        set_clauses = []
        params = []
        idx = 3
        for key, val in updates.items():
            set_clauses.append(f"{key} = ${idx}")
            params.append(val)
            idx += 1
        set_clauses.append("updated_at = now()")

        query = f"""UPDATE calendars SET {', '.join(set_clauses)}
                    WHERE id = $1 AND owner_email = $2
                    RETURNING *"""
        row = await db.fetchrow(query, calendar_id, user, *params)
        return _row_to_calendar(row)

    async def delete_calendar(
        self, db: asyncpg.Pool, user: str, calendar_id: uuid.UUID
    ) -> bool:
        row = await db.fetchrow(
            "SELECT * FROM calendars WHERE id = $1 AND owner_email = $2",
            calendar_id,
            user,
        )
        if not row:
            raise ValueError("Calendar not found")
        if row["is_default"]:
            raise ValueError("Cannot delete default calendar")

        await db.execute("DELETE FROM calendars WHERE id = $1", calendar_id)
        return True

    # Ã¢ÂÂÃ¢ÂÂ Events Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

    async def create_event(
        self, db: asyncpg.Pool, user: str, data: EventCreate
    ) -> EventOut:
        # Verify calendar ownership
        cal = await db.fetchrow(
            "SELECT * FROM calendars WHERE id = $1 AND owner_email = $2",
            data.calendar_id,
            user,
        )
        if not cal:
            raise ValueError("Calendar not found")

        uid = generate_uid()

        # Build iCal
        event_dict = {
            "uid": uid,
            "summary": strip_html(data.summary),
            "description": data.description,
            "location": data.location,
            "dtstart": data.dtstart,
            "dtend": data.dtend,
            "all_day": data.all_day,
            "rrule": data.rrule,
            "status": "CONFIRMED",
            "transparency": "OPAQUE",
            "timezone": data.timezone,
            "reminders": data.reminders,
            "attendees": _merge_attendees(data),
        }
        vcal_str = build_vcalendar(event_dict)

        # Write to Radicale
        await radicale_client.put_event(user, cal["radicale_path"], uid, vcal_str)

        # Insert into PostgreSQL
        row = await db.fetchrow(
            """INSERT INTO events
               (calendar_id, uid, summary, description, location,
                dtstart, dtend, all_day, rrule, status, transparency,
                timezone, reminders, attendees)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb,$14::jsonb)
               RETURNING *""",
            data.calendar_id,
            uid,
            data.summary,
            data.description,
            data.location,
            data.dtstart,
            data.dtend,
            data.all_day,
            data.rrule,
            "CONFIRMED",
            "OPAQUE",
            data.timezone,
            json.dumps(data.reminders),
            json.dumps(_merge_attendees(data)),
        )

        # Auto-invite attendees
        merged_att = _merge_attendees(data)
        if merged_att:
            try:
                await self._auto_invite_attendees(db, user, row, merged_att)
            except Exception as e:
                logger.warning("Auto-invite failed: %s", e)

        return EventOut(
            id=row["id"],
            calendar_id=row["calendar_id"],
            uid=row["uid"],
            summary=row["summary"],
            description=row["description"] or "",
            location=row["location"] or "",
            dtstart=row["dtstart"],
            dtend=row["dtend"],
            all_day=row["all_day"],
            rrule=row["rrule"] or "",
            status=row["status"] or "CONFIRMED",
            color=cal["color"],
            calendar_name=cal["name"],
            timezone=row["timezone"] or "America/Guayaquil",
            reminders=data.reminders,
            attendees=_merge_attendees(data),
        )

    async def list_events(
        self,
        db: asyncpg.Pool,
        user: str,
        start: datetime,
        end: datetime,
        calendar_id: Optional[uuid.UUID] = None,
    ) -> list[EventOut]:
        if calendar_id:
            rows = await db.fetch(
                """SELECT e.*, c.color, c.name AS calendar_name
                   FROM events e
                   JOIN calendars c ON c.id = e.calendar_id
                   WHERE c.owner_email = $1
                     AND e.calendar_id = $2
                     AND e.dtstart < $4
                     AND e.dtend > $3
                   ORDER BY e.dtstart""",
                user,
                calendar_id,
                start,
                end,
            )
        else:
            rows = await db.fetch(
                """SELECT e.*, c.color, c.name AS calendar_name
                   FROM events e
                   JOIN calendars c ON c.id = e.calendar_id
                   WHERE c.owner_email = $1
                     AND e.dtstart < $3
                     AND e.dtend > $2
                   ORDER BY e.dtstart""",
                user,
                start,
                end,
            )
        # Expand recurrent events within the requested range
        result: list[EventOut] = []
        for r in rows:
            ev = _row_to_event(r)
            if ev.rrule:
                result.extend(_expand_recurrence(ev, start, end))
            else:
                result.append(ev)
        result.sort(key=lambda e: e.dtstart)
        return result

    async def get_event(
        self, db: asyncpg.Pool, user: str, event_id: uuid.UUID
    ) -> EventOut:
        row = await db.fetchrow(
            """SELECT e.*, c.color, c.name AS calendar_name
               FROM events e
               JOIN calendars c ON c.id = e.calendar_id
               WHERE e.id = $1 AND c.owner_email = $2""",
            event_id,
            user,
        )
        if not row:
            raise ValueError("Event not found")
        return _row_to_event(row)

    async def update_event(
        self, db: asyncpg.Pool, user: str, event_id: uuid.UUID, data: EventUpdate
    ) -> EventOut:
        # Get existing event
        existing = await db.fetchrow(
            """SELECT e.*, c.radicale_path, c.color, c.name AS calendar_name
               FROM events e
               JOIN calendars c ON c.id = e.calendar_id
               WHERE e.id = $1 AND c.owner_email = $2""",
            event_id,
            user,
        )
        if not existing:
            raise ValueError("Event not found")

        updates = data.model_dump(exclude_none=True)
        if not updates:
            return _row_to_event(existing)

        # Sanitize text fields
        if "summary" in updates:
            updates["summary"] = strip_html(updates["summary"])
        if "description" in updates:
            updates["description"] = sanitize_html(updates["description"] or "")

        # Merge attendees with optional_attendees into proper format
        if "attendees" in updates or "optional_attendees" in updates:
            merged = []
            for a in updates.get("attendees") or []:
                if isinstance(a, str):
                    merged.append({"email": a, "role": "REQ-PARTICIPANT"})
                elif isinstance(a, dict):
                    a.setdefault("role", "REQ-PARTICIPANT")
                    merged.append(a)
            for a in updates.get("optional_attendees") or []:
                if isinstance(a, str):
                    merged.append({"email": a, "role": "OPT-PARTICIPANT"})
                elif isinstance(a, dict):
                    a["role"] = "OPT-PARTICIPANT"
                    merged.append(a)
            updates["attendees"] = merged

        # Build SET clause
        set_clauses = []
        params = []
        idx = 3
        # Si cambia el horario o los recordatorios, re-armar el aviso
        if "dtstart" in updates or "reminders" in updates:
            set_clauses.append("reminder_sent_at = NULL")
        for key, val in updates.items():
            if key == "optional_attendees":
                continue  # already merged into attendees above
            if key in ("reminders", "attendees"):
                set_clauses.append(f"{key} = ${idx}::jsonb")
                params.append(json.dumps(val))
            else:
                set_clauses.append(f"{key} = ${idx}")
                params.append(val)
            idx += 1
        set_clauses.append("updated_at = now()")

        query = f"""UPDATE events SET {', '.join(set_clauses)}
                    WHERE id = $1 AND calendar_id IN (
                        SELECT id FROM calendars WHERE owner_email = $2
                    )
                    RETURNING *"""
        row = await db.fetchrow(query, event_id, user, *params)

        # Get calendar info for response
        cal = await db.fetchrow(
            "SELECT * FROM calendars WHERE id = $1", row["calendar_id"]
        )

        # Rebuild iCal and update Radicale
        event_dict = {
            "uid": row["uid"],
            "summary": row["summary"],
            "description": row["description"],
            "location": row["location"],
            "dtstart": row["dtstart"],
            "dtend": row["dtend"],
            "all_day": row["all_day"],
            "rrule": row["rrule"],
            "status": row["status"],
            "transparency": row["transparency"],
            "timezone": row["timezone"],
            "reminders": (
                json.loads(row["reminders"])
                if isinstance(row["reminders"], str)
                else (row["reminders"] or [])
            ),
            "attendees": (
                json.loads(row["attendees"])
                if isinstance(row["attendees"], str)
                else (row["attendees"] or [])
            ),
        }
        vcal_str = build_vcalendar(event_dict)
        await radicale_client.put_event(
            user, cal["radicale_path"], row["uid"], vcal_str
        )

        # Auto-invite attendees on update
        if event_dict["attendees"]:
            try:
                await self._auto_invite_attendees(
                    db, user, row, event_dict["attendees"]
                )
            except Exception as e:
                logger.warning("Auto-invite on update failed: %s", e)

        return EventOut(
            id=row["id"],
            calendar_id=row["calendar_id"],
            uid=row["uid"],
            summary=row["summary"],
            description=row["description"] or "",
            location=row["location"] or "",
            dtstart=row["dtstart"],
            dtend=row["dtend"],
            all_day=row["all_day"],
            rrule=row["rrule"] or "",
            status=row["status"] or "CONFIRMED",
            color=cal["color"],
            calendar_name=cal["name"],
            timezone=row["timezone"] or "America/Guayaquil",
            reminders=event_dict["reminders"],
            attendees=event_dict["attendees"],
        )

    async def move_event(
        self, db: asyncpg.Pool, user: str, event_id: uuid.UUID, data: EventMove
    ) -> EventOut:
        """Quick move (drag & drop) — only updates dtstart/dtend."""
        update = EventUpdate(dtstart=data.dtstart, dtend=data.dtend)
        return await self.update_event(db, user, event_id, update)

    async def delete_event(
        self, db: asyncpg.Pool, user: str, event_id: uuid.UUID
    ) -> bool:
        row = await db.fetchrow(
            """SELECT e.uid, c.radicale_path
               FROM events e
               JOIN calendars c ON c.id = e.calendar_id
               WHERE e.id = $1 AND c.owner_email = $2""",
            event_id,
            user,
        )
        if not row:
            raise ValueError("Event not found")

        # Delete from Radicale
        await radicale_client.delete_event(user, row["radicale_path"], row["uid"])

        # Delete from PostgreSQL
        await db.execute("DELETE FROM events WHERE id = $1", event_id)
        return True

    async def export_calendar(
        self, db: asyncpg.Pool, user: str, calendar_id: uuid.UUID
    ) -> str:
        """Export all events of a calendar as a single .ics file."""
        cal = await db.fetchrow(
            "SELECT * FROM calendars WHERE id = $1 AND owner_email = $2",
            calendar_id,
            user,
        )
        if not cal:
            raise ValueError("Calendar not found")

        rows = await db.fetch(
            "SELECT * FROM events WHERE calendar_id = $1 ORDER BY dtstart",
            calendar_id,
        )

        from icalendar import Calendar as ICal

        ical = ICal()
        ical.add("prodid", f"-//{app_name_cacheado()}//Calendar//ES")
        ical.add("version", "2.0")
        ical.add("calscale", "GREGORIAN")
        ical.add("x-wr-calname", cal["name"])

        for row in rows:
            reminders = row["reminders"]
            if isinstance(reminders, str):
                reminders = json.loads(reminders)
            attendees = row["attendees"]
            if isinstance(attendees, str):
                attendees = json.loads(attendees)

            event_dict = {
                "uid": row["uid"],
                "summary": row["summary"],
                "description": row["description"] or "",
                "location": row["location"] or "",
                "dtstart": row["dtstart"],
                "dtend": row["dtend"],
                "all_day": row["all_day"],
                "rrule": row["rrule"] or "",
                "status": row["status"] or "CONFIRMED",
                "transparency": row["transparency"] or "OPAQUE",
                "timezone": row["timezone"] or "America/Guayaquil",
                "reminders": reminders or [],
                "attendees": attendees or [],
            }
            # Build individual event and extract VEVENT component
            vcal_str = build_vcalendar(event_dict)
            from icalendar import Calendar as ICalParse

            parsed = ICalParse.from_ical(vcal_str)
            for comp in parsed.walk():
                if comp.name == "VEVENT":
                    ical.add_component(comp)
                    break

        return ical.to_ical().decode("utf-8")

    # Ã¢ÂÂÃ¢ÂÂ Calendar Sharing Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

    async def share_calendar(
        self,
        db: asyncpg.Pool,
        owner: str,
        calendar_id: uuid.UUID,
        shared_with: str,
        permission: str,
    ) -> dict:
        """Compartir un calendario con otro usuario."""
        cal = await db.fetchrow(
            "SELECT * FROM calendars WHERE id = $1 AND owner_email = $2",
            calendar_id,
            owner,
        )
        if not cal:
            raise ValueError("Calendario no encontrado o no autorizado")
        if shared_with == owner:
            raise ValueError("No puede compartirse el calendario consigo mismo")
        # Upsert
        row = await db.fetchrow(
            """INSERT INTO calendar_shares (calendar_id, owner_email, shared_with, permission)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (calendar_id, shared_with)
               DO UPDATE SET permission = EXCLUDED.permission
               RETURNING *""",
            calendar_id,
            owner,
            shared_with,
            permission,
        )
        return {
            "id": row["id"],
            "calendar_id": row["calendar_id"],
            "calendar_name": cal["name"],
            "calendar_color": cal["color"],
            "owner_email": row["owner_email"],
            "shared_with": row["shared_with"],
            "permission": row["permission"],
            "created_at": row["created_at"],
        }

    async def list_shared_with_me(self, db: asyncpg.Pool, user: str) -> list[dict]:
        """Listar calendarios compartidos conmigo."""
        rows = await db.fetch(
            """SELECT cs.*, c.name AS calendar_name, c.color AS calendar_color
               FROM calendar_shares cs
               JOIN calendars c ON c.id = cs.calendar_id
               WHERE cs.shared_with = $1
               ORDER BY cs.created_at""",
            user,
        )
        return [dict(r) for r in rows]

    async def list_shares_of_calendar(
        self, db: asyncpg.Pool, owner: str, calendar_id: uuid.UUID
    ) -> list[dict]:
        """Listar con quiénes está compartido un calendario mío."""
        cal = await db.fetchrow(
            "SELECT id FROM calendars WHERE id = $1 AND owner_email = $2",
            calendar_id,
            owner,
        )
        if not cal:
            raise ValueError("Calendario no encontrado o no autorizado")
        rows = await db.fetch(
            """SELECT cs.*, c.name AS calendar_name, c.color AS calendar_color
               FROM calendar_shares cs
               JOIN calendars c ON c.id = cs.calendar_id
               WHERE cs.calendar_id = $1
               ORDER BY cs.shared_with""",
            calendar_id,
        )
        return [dict(r) for r in rows]

    async def revoke_share(
        self, db: asyncpg.Pool, owner: str, calendar_id: uuid.UUID, shared_with: str
    ) -> bool:
        """Revocar acceso compartido."""
        cal = await db.fetchrow(
            "SELECT id FROM calendars WHERE id = $1 AND owner_email = $2",
            calendar_id,
            owner,
        )
        if not cal:
            raise ValueError("Calendario no encontrado o no autorizado")
        result = await db.execute(
            "DELETE FROM calendar_shares WHERE calendar_id = $1 AND shared_with = $2",
            calendar_id,
            shared_with,
        )
        return True

    async def list_events_shared(
        self,
        db: asyncpg.Pool,
        user: str,
        start: datetime,
        end: datetime,
    ) -> list[EventOut]:
        """Listar eventos de calendarios compartidos conmigo."""
        rows = await db.fetch(
            """SELECT e.*, c.color, c.name AS calendar_name
               FROM events e
               JOIN calendars c ON c.id = e.calendar_id
               JOIN calendar_shares cs ON cs.calendar_id = c.id
               WHERE cs.shared_with = $1
                 AND e.dtstart < $3
                 AND e.dtend > $2
               ORDER BY e.dtstart""",
            user,
            start,
            end,
        )
        return [_row_to_event(r) for r in rows]

    # Ã¢ÂÂÃ¢ÂÂ Event Invitations Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

    async def _auto_invite_attendees(
        self, db: asyncpg.Pool, organizer: str, event_row, attendees: list
    ):
        """Auto-create event in attendee calendars and send email notifications."""
        if not attendees:
            return
        import smtplib
        from email import encoders
        from email.mime.base import MIMEBase
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.utils import formatdate

        for att in attendees:
            email = att if isinstance(att, str) else att.get("email", "")
            if not email or email == organizer:
                continue

            # 1. Create event in attendee's calendar (if they have an account)
            try:
                att_cal = await db.fetchrow(
                    "SELECT * FROM calendars WHERE owner_email = $1 AND is_default = true",
                    email,
                )
                if not att_cal:
                    # Try with @ejemplo.com version
                    alt_email = email.replace("@ejemplo.com", "@ejemplo.com")
                    att_cal = await db.fetchrow(
                        "SELECT * FROM calendars WHERE owner_email = $1 AND is_default = true",
                        alt_email,
                    )
                if att_cal:
                    # Check if event already exists (by uid) in attendee's calendar
                    existing = await db.fetchrow(
                        "SELECT id FROM events WHERE uid = $1 AND calendar_id = $2",
                        event_row["uid"],
                        att_cal["id"],
                    )
                    if not existing:
                        await db.execute(
                            """INSERT INTO events
                               (calendar_id, uid, summary, description, location,
                                dtstart, dtend, all_day, rrule, status, transparency,
                                timezone, reminders, attendees)
                               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb,$14::jsonb)""",
                            att_cal["id"],
                            event_row["uid"],
                            event_row["summary"],
                            event_row["description"],
                            event_row["location"],
                            event_row["dtstart"],
                            event_row["dtend"],
                            event_row["all_day"],
                            event_row["rrule"],
                            "CONFIRMED",
                            "OPAQUE",
                            event_row["timezone"],
                            (
                                json.dumps(
                                    event_row["reminders"]
                                    if event_row["reminders"]
                                    else []
                                )
                                if not isinstance(event_row["reminders"], str)
                                else event_row["reminders"]
                            ),
                            json.dumps(
                                [{"email": organizer, "role": "ORGANIZER"}]
                                + list(attendees)
                            ),
                        )
                    else:
                        # Update existing
                        await db.execute(
                            """UPDATE events SET summary=$1, description=$2, location=$3,
                               dtstart=$4, dtend=$5, all_day=$6, rrule=$7, timezone=$8,
                               attendees=$9::jsonb, updated_at=now()
                               WHERE uid = $10 AND calendar_id = $11""",
                            event_row["summary"],
                            event_row["description"],
                            event_row["location"],
                            event_row["dtstart"],
                            event_row["dtend"],
                            event_row["all_day"],
                            event_row["rrule"],
                            event_row["timezone"],
                            json.dumps(
                                [{"email": organizer, "role": "ORGANIZER"}]
                                + list(attendees)
                            ),
                            event_row["uid"],
                            att_cal["id"],
                        )
            except Exception as e:
                logger.warning(
                    "Could not create event in attendee %s calendar: %s", email, e
                )

            # 2. Send email notification
            try:
                from zoneinfo import ZoneInfo

                tz = ZoneInfo(event_row.get("timezone") or "America/Guayaquil")
                dtstart_str = (
                    event_row["dtstart"].astimezone(tz).strftime("%d/%m/%Y %H:%M")
                    if event_row["dtstart"]
                    else ""
                )
                dtend_str = (
                    event_row["dtend"].astimezone(tz).strftime("%d/%m/%Y %H:%M")
                    if event_row["dtend"]
                    else ""
                )

                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"Invitación: {event_row['summary']}"
                msg["From"] = organizer
                msg["To"] = email
                msg["Date"] = formatdate(localtime=True)

                body = (
                    f"<h3>Ha sido invitado a un evento</h3>"
                    f"<p><b>{event_row['summary']}</b></p>"
                    f"<p>Inicio: {dtstart_str}<br>"
                    f"Fin: {dtend_str}<br>"
                    f"Lugar: {event_row.get('location', '') or ''}<br></p>"
                    f"<p>{event_row.get('description', '') or ''}</p>"
                    f"<p>Organizador: {organizer}</p>"
                    f"<hr><p><small>Este evento ha sido agregado a su calendario automáticamente.</small></p>"
                )
                msg.attach(MIMEText(body, "html", "utf-8"))

                # ICS (METHOD:REQUEST) para que la invitación se vea como tarjeta
                # con RSVP (Aceptar/Tentativa/Rechazar), igual que send_invitations.
                # Sin esto el correo salía solo en HTML y se veía como texto plano.
                try:
                    from app.calendar.ical_utils import build_vcalendar

                    ics = build_vcalendar(
                        {
                            "uid": event_row["uid"],
                            "summary": event_row["summary"],
                            "description": event_row.get("description", "") or "",
                            "location": event_row.get("location", "") or "",
                            "dtstart": event_row["dtstart"],
                            "dtend": event_row["dtend"],
                            "all_day": event_row.get("all_day", False),
                            "rrule": event_row.get("rrule", "") or "",
                            "status": event_row.get("status", "CONFIRMED")
                            or "CONFIRMED",
                            "timezone": event_row.get("timezone")
                            or "America/Guayaquil",
                            "attendees": list(attendees),
                            "method": "REQUEST",
                            "organizer": organizer,
                        }
                    )
                    cal_part = MIMEText(ics, "calendar", "utf-8")
                    cal_part.replace_header(
                        "Content-Type", 'text/calendar; method=REQUEST; charset="utf-8"'
                    )
                    cal_part.add_header(
                        "Content-Disposition", 'attachment; filename="invite.ics"'
                    )
                    msg.attach(cal_part)
                except Exception as _ics_exc:
                    logger.warning(
                        "auto-invite: no se pudo adjuntar invite.ics: %s", _ics_exc
                    )

                with smtplib.SMTP("127.0.0.1", 25) as s:
                    s.sendmail(organizer, [email], msg.as_string())
                logger.info(
                    "Invitation sent to %s for event %s", email, event_row["summary"]
                )
            except Exception as e:
                logger.warning("Could not send invitation to %s: %s", email, e)

    async def send_invitations(
        self, db: asyncpg.Pool, user: str, event_id: uuid.UUID, smtp_config: dict
    ) -> int:
        """Enviar emails de invitación a los asistentes de un evento."""
        row = await db.fetchrow(
            """SELECT e.*, c.name AS calendar_name, c.owner_email
               FROM events e
               JOIN calendars c ON c.id = e.calendar_id
               WHERE e.id = $1 AND c.owner_email = $2""",
            event_id,
            user,
        )
        if not row:
            raise ValueError("Evento no encontrado")
        attendees_raw = row["attendees"]
        if isinstance(attendees_raw, str):
            import json as _json

            attendees_raw = _json.loads(attendees_raw)
        if not attendees_raw:
            return 0
        import html as _html
        import re as _re
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.utils import formatdate

        sent = 0

        from zoneinfo import ZoneInfo

        _tz = ZoneInfo(row.get("timezone") or "America/Guayaquil")
        _DIAS = [
            "lunes",
            "martes",
            "miércoles",
            "jueves",
            "viernes",
            "sábado",
            "domingo",
        ]
        _MESES = [
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        ]

        def _fecha_linda(dt):
            if not dt:
                return ""
            d = dt.astimezone(_tz)
            return f"{_DIAS[d.weekday()].capitalize()}, {d.day} de {_MESES[d.month-1]} de {d.year} · {d.strftime('%H:%M')}"

        _inicio = _fecha_linda(row["dtstart"])
        _fin = row["dtend"].astimezone(_tz).strftime("%H:%M") if row["dtend"] else ""
        _lugar = row.get("location", "") or ""
        _desc = row.get("description", "") or ""
        # Detectar enlace de reunión (Jitsi u otro) en lugar o descripción
        _m = _re.search(r"https?://\S+", _lugar) or _re.search(r"https?://\S+", _desc)
        _join_url = _m.group(0).rstrip(".,)") if _m else ""

        def _cuerpo_html(titulo_cabecera: str, es_organizador: bool = False) -> str:
            esc = _html.escape
            boton = ""
            if _join_url:
                boton_moderador = ""
                if es_organizador and "meet.maquita.com.ec/" in _join_url:
                    _sala = _join_url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
                    _mod_url = (
                        f"https://datos.maquita.com.ec/reuniones/unirse?sala={_sala}"
                    )
                    boton_moderador = (
                        f"<br><a href='{esc(_mod_url)}' style='background:#107c10;color:#ffffff;"
                        f"text-decoration:none;padding:10px 24px;border-radius:4px;font-size:14px;"
                        f"font-weight:600;display:inline-block;margin-top:10px;'>"
                        f"<span style='color:#ffffff !important;'>🛡️ Entrar como moderador (con tu cuenta FARO)</span></a>"
                        f"<p style='font-size:11px;color:#605e5c;margin:6px 0 0;'>"
                        f"Como organizador, entra por este botón: FARO te autentica y te da el control de la sala.</p>"
                    )
                boton = (
                    f"<div style='margin:20px 0;text-align:center;'>"
                    f"<a href='{esc(_join_url)}' style='background:#0078d4;color:#ffffff;"
                    f"text-decoration:none;padding:12px 28px;border-radius:4px;font-size:15px;"
                    f"font-weight:600;display:inline-block;'>"
                    f"<span style='color:#ffffff !important;'>🎥 Unirse a la reunión</span></a>"
                    + boton_moderador
                    + f"<p style='font-size:12px;color:#605e5c;margin:10px 0 0;'>"
                    f"Si el botón no funciona, copia y pega este enlace en tu navegador:<br>"
                    f"<a href='{esc(_join_url)}' style='color:#0078d4;word-break:break-all;'>{esc(_join_url)}</a></p>"
                    f"</div>"
                )
            fila = lambda et, val: (
                (
                    f"<tr><td style='padding:6px 12px 6px 0;color:#605e5c;font-size:13px;"
                    f"white-space:nowrap;vertical-align:top;'>{et}</td>"
                    f"<td style='padding:6px 0;color:#323130;font-size:13px;'>{val}</td></tr>"
                )
                if val
                else ""
            )
            cuando = esc(_inicio) + (f" – {esc(_fin)}" if _fin else "")
            lugar_html = esc(_lugar)
            if _join_url and _join_url in _lugar:
                lugar_html = f"<a href='{esc(_join_url)}' style='color:#0078d4;'>{esc(_join_url)}</a>"
            return (
                "<div style='font-family:Segoe UI,Arial,sans-serif;max-width:560px;margin:0 auto;"
                "border:1px solid #edebe9;border-radius:8px;overflow:hidden;'>"
                f"<div style='background:#0078d4;color:#ffffff;padding:18px 24px;'>"
                f"<div style='font-size:12px;opacity:.85;margin-bottom:4px;'>{esc(titulo_cabecera)}</div>"
                f"<div style='font-size:19px;font-weight:600;'>📅 {esc(row['summary'])}</div>"
                f"</div>"
                f"<div style='padding:20px 24px;background:#ffffff;'>"
                f"<table style='border-collapse:collapse;width:100%;'>"
                + fila("🕒 Cuándo", cuando)
                + fila("📍 Lugar", lugar_html)
                + fila("👤 Organizador", esc(user))
                + (
                    fila("📝 Detalles", esc(_desc).replace(chr(10), "<br>"))
                    if _desc
                    else ""
                )
                + "</table>"
                + boton
                + "<p style='font-size:12px;color:#605e5c;border-top:1px solid #edebe9;"
                "padding-top:12px;margin-top:16px;'>Puedes responder con los botones "
                "<b>Aceptar / Rechazar / Provisional</b> de tu cliente de correo "
                f"({app_name_cacheado()}, Outlook, Thunderbird…). El evento se añadió "
                "automáticamente a tu calendario.</p>"
                "</div>"
                "<div style='background:#faf9f8;padding:10px 24px;font-size:11px;color:#a19f9d;'>"
                f"{app_name_cacheado()} · {org_name_cacheado()}</div>"
                "</div>"
            )

        # Destinatarios: asistentes + copia para el organizador (con su enlace)
        _destinos = []
        for att in attendees_raw:
            _e = att if isinstance(att, str) else att.get("email", "")
            if _e:
                _destinos.append(
                    (_e, "Invitación a evento", f"Invitación: {row['summary']}", True)
                )
        _destinos.append(
            (
                user,
                "Confirmación — evento creado",
                f"Tu evento: {row['summary']}",
                False,
            )
        )

        for email, _cab, _subj, _con_ics in _destinos:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = _subj
                msg["From"] = user
                msg["To"] = email
                msg["Date"] = formatdate(localtime=True)
                body = _cuerpo_html(_cab, es_organizador=not _con_ics)
                msg.attach(MIMEText(body, "html"))

                # Invite iCalendar (METHOD:REQUEST) → habilita RSVP nativo en
                # Outlook/Thunderbird y el banner inline del propio webmail.
                # (la copia del organizador va sin ics: él no se auto-responde)
                try:
                    if not _con_ics:
                        raise StopIteration()
                    from email.mime.base import MIMEBase

                    from app.calendar.ical_utils import build_vcalendar

                    _att_list = attendees_raw if isinstance(attendees_raw, list) else []
                    ics = build_vcalendar(
                        {
                            "uid": row.get("uid") or str(row["id"]),
                            "summary": row["summary"],
                            "description": row.get("description", "") or "",
                            "location": row.get("location", "") or "",
                            "dtstart": row["dtstart"],
                            "dtend": row["dtend"],
                            "all_day": row.get("all_day", False),
                            "rrule": row.get("rrule", "") or "",
                            "status": row.get("status", "CONFIRMED") or "CONFIRMED",
                            "timezone": row.get("timezone") or "America/Guayaquil",
                            "attendees": _att_list,
                            "method": "REQUEST",
                            "organizer": user,
                        }
                    )
                    cal_part = MIMEText(ics, "calendar", "utf-8")
                    cal_part.replace_header(
                        "Content-Type", 'text/calendar; method=REQUEST; charset="utf-8"'
                    )
                    cal_part.add_header(
                        "Content-Disposition", 'attachment; filename="invite.ics"'
                    )
                    msg.attach(cal_part)
                except StopIteration:
                    pass
                except Exception as _ics_exc:
                    logger.warning("No se pudo adjuntar invite.ics: %s", _ics_exc)

                with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as s:
                    try:
                        s.starttls()
                    except smtplib.SMTPNotSupportedError:
                        pass
                    if smtp_config.get("password"):
                        try:
                            s.login(user, smtp_config["password"])
                        except smtplib.SMTPNotSupportedError:
                            pass
                    s.sendmail(user, [email], msg.as_string())
                sent += 1
            except Exception as e:
                logger.warning("No se pudo enviar invitación a %s: %s", email, e)
        return sent

    async def respond_invitation(
        self, db: asyncpg.Pool, user: str, event_id: uuid.UUID, status: str
    ) -> dict:
        """Registrar respuesta del asistente a un evento."""
        if status not in ("accepted", "declined", "tentative"):
            raise ValueError("Estado inválido")
        # Verificar que el usuario es asistente del evento
        event_row = await db.fetchrow("SELECT * FROM events WHERE id = $1", event_id)
        if not event_row:
            raise ValueError("Evento no encontrado")
        attendees_raw = event_row["attendees"]
        if isinstance(attendees_raw, str):
            import json as _json

            attendees_raw = _json.loads(attendees_raw)
        emails = [
            a if isinstance(a, str) else a.get("email", "")
            for a in (attendees_raw or [])
        ]
        if user not in emails:
            # También aceptar si el evento es compartido con el usuario
            pass
        # Registrar en public.event_invitations
        await db.execute(
            """INSERT INTO event_invitations (event_id, attendee_email, status, responded_at)
               VALUES ($1, $2, $3, NOW())
               ON CONFLICT (event_id, attendee_email)
               DO UPDATE SET status = EXCLUDED.status, responded_at = NOW()""",
            event_id,
            user,
            status,
        )
        return {"event_id": str(event_id), "status": status, "user": user}

    # Ã¢ÂÂÃ¢ÂÂ Free/Busy Ã¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂÃ¢ÂÂ

    async def freebusy(
        self,
        db: asyncpg.Pool,
        target_user: str,
        start: datetime,
        end: datetime,
    ) -> list[dict]:
        """Return busy time slots for target_user in [start, end].

        Only returns start/end of each busy block -- no event details (privacy).
        Also expands recurrent events.
        """
        rows = await db.fetch(
            """SELECT e.dtstart, e.dtend, e.rrule
               FROM events e
               JOIN calendars c ON c.id = e.calendar_id
               WHERE c.owner_email = $1
                 AND e.dtstart < $3
                 AND e.dtend > $2
                 AND e.all_day = FALSE
                 AND e.status <> 'CANCELLED'
                 AND COALESCE(e.transparency, 'OPAQUE') != 'TRANSPARENT'
               ORDER BY e.dtstart""",
            target_user,
            start,
            end,
        )
        slots: list[dict] = []
        for r in rows:
            rrule_str = r["rrule"] or ""
            if rrule_str:
                try:
                    duration = r["dtend"] - r["dtstart"]
                    dtstart_str = r["dtstart"].strftime("%Y%m%dT%H%M%S")
                    rrule_text = f"DTSTART:{dtstart_str}\n{rrule_str}"
                    rule = rrulestr(rrule_text, ignoretz=True)
                    for i, occ in enumerate(rule):
                        if i > 500:
                            break
                        occ_end = occ + duration
                        if occ_end <= start:
                            continue
                        if occ >= end:
                            break
                        slots.append(
                            {"start": occ.isoformat(), "end": occ_end.isoformat()}
                        )
                except Exception:
                    slots.append(
                        {
                            "start": r["dtstart"].isoformat(),
                            "end": r["dtend"].isoformat(),
                        }
                    )
            else:
                slots.append(
                    {"start": r["dtstart"].isoformat(), "end": r["dtend"].isoformat()}
                )
        slots.sort(key=lambda s: s["start"])
        return slots


calendar_service = CalendarService()
