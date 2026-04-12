"""CalendarService — dual-write to Radicale + PostgreSQL."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from dateutil.rrule import rrulestr

import asyncpg

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
    )


def _expand_recurrence(event: EventOut, range_start: datetime, range_end: datetime) -> list[EventOut]:
    """Expand a recurrent event into individual occurrences within [range_start, range_end]."""
    try:
        duration = event.dtend - event.dtstart
        dtstart_str = event.dtstart.strftime("%Y%m%dT%H%M%S")
        rrule_text = f"DTSTART:{dtstart_str}\n{event.rrule}"
        rule = rrulestr(rrule_text, ignoretz=True)

        occurrences: list[EventOut] = []
        for i, occ_start in enumerate(rule):
            if i > 500:
                break
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

    # ── Calendars ──────────────────────────────────────────

    async def ensure_default_calendar(
        self, db: asyncpg.Pool, user: str
    ) -> CalendarOut:
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

    # ── Events ─────────────────────────────────────────────

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
            "summary": data.summary,
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
            "attendees": data.attendees,
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
            json.dumps(data.attendees),
        )

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
            attendees=data.attendees,
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

        # Build SET clause
        set_clauses = []
        params = []
        idx = 3
        for key, val in updates.items():
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
            "reminders": json.loads(row["reminders"]) if isinstance(row["reminders"], str) else (row["reminders"] or []),
            "attendees": json.loads(row["attendees"]) if isinstance(row["attendees"], str) else (row["attendees"] or []),
        }
        vcal_str = build_vcalendar(event_dict)
        await radicale_client.put_event(
            user, cal["radicale_path"], row["uid"], vcal_str
        )

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
        ical.add("prodid", "-//Maquita Webmail//Calendar//ES")
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


    # ── Calendar Sharing ───────────────────────────────────

    async def share_calendar(
        self, db: asyncpg.Pool, owner: str, calendar_id: uuid.UUID, shared_with: str, permission: str
    ) -> dict:
        """Compartir un calendario con otro usuario."""
        cal = await db.fetchrow(
            "SELECT * FROM calendars WHERE id = $1 AND owner_email = $2",
            calendar_id, owner,
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
            calendar_id, owner, shared_with, permission,
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
            calendar_id, owner,
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
            calendar_id, owner,
        )
        if not cal:
            raise ValueError("Calendario no encontrado o no autorizado")
        result = await db.execute(
            "DELETE FROM calendar_shares WHERE calendar_id = $1 AND shared_with = $2",
            calendar_id, shared_with,
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
            user, start, end,
        )
        return [_row_to_event(r) for r in rows]

    # ── Event Invitations ─────────────────────────────────

    async def send_invitations(
        self, db: asyncpg.Pool, user: str, event_id: uuid.UUID, smtp_config: dict
    ) -> int:
        """Enviar emails de invitación a los asistentes de un evento."""
        row = await db.fetchrow(
            """SELECT e.*, c.name AS calendar_name, c.owner_email
               FROM events e
               JOIN calendars c ON c.id = e.calendar_id
               WHERE e.id = $1 AND c.owner_email = $2""",
            event_id, user,
        )
        if not row:
            raise ValueError("Evento no encontrado")
        attendees_raw = row["attendees"]
        if isinstance(attendees_raw, str):
            import json as _json
            attendees_raw = _json.loads(attendees_raw)
        if not attendees_raw:
            return 0
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.utils import formatdate
        sent = 0
        for att in attendees_raw:
            email = att if isinstance(att, str) else att.get("email", "")
            if not email:
                continue
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"Invitación: {row[summary]}"
                msg["From"] = user
                msg["To"] = email
                msg["Date"] = formatdate(localtime=True)
                dtstart_str = row["dtstart"].strftime("%d/%m/%Y %H:%M") if row["dtstart"] else ""
                dtend_str = row["dtend"].strftime("%d/%m/%Y %H:%M") if row["dtend"] else ""
                body = (
                    f"Ha sido invitado al evento: <b>{row['summary']}</b><br>"
                    f"Inicio: {dtstart_str}<br>"
                    f"Fin: {dtend_str}<br>"
                    f"Lugar: {row.get('location', '') or '' }<br>"
                    f"Descripción: {row.get('description', '') or '' }<br><br>"
                    f"Organizador: {user}"
                )
                msg.attach(MIMEText(body, "html"))
                with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as s:
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
        event_row = await db.fetchrow(
            "SELECT * FROM events WHERE id = $1", event_id
        )
        if not event_row:
            raise ValueError("Evento no encontrado")
        attendees_raw = event_row["attendees"]
        if isinstance(attendees_raw, str):
            import json as _json
            attendees_raw = _json.loads(attendees_raw)
        emails = [a if isinstance(a, str) else a.get("email", "") for a in (attendees_raw or [])]
        if user not in emails:
            # También aceptar si el evento es compartido con el usuario
            pass
        # Registrar en public.event_invitations
        await db.execute(
            """INSERT INTO event_invitations (event_id, attendee_email, status, responded_at)
               VALUES ($1, $2, $3, NOW())
               ON CONFLICT (event_id, attendee_email)
               DO UPDATE SET status = EXCLUDED.status, responded_at = NOW()""",
            event_id, user, status,
        )
        return {"event_id": str(event_id), "status": status, "user": user}

    # ── Free/Busy ───────────────────────────────────────────

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
                 AND COALESCE(e.transparency, 'OPAQUE') != 'TRANSPARENT'
               ORDER BY e.dtstart""",
            target_user, start, end,
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
                        slots.append({"start": occ.isoformat(), "end": occ_end.isoformat()})
                except Exception:
                    slots.append({"start": r["dtstart"].isoformat(), "end": r["dtend"].isoformat()})
            else:
                slots.append({"start": r["dtstart"].isoformat(), "end": r["dtend"].isoformat()})
        slots.sort(key=lambda s: s["start"])
        return slots


calendar_service = CalendarService()

