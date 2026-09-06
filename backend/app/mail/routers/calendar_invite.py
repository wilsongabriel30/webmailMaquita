"""Calendar invitation RSVP router — accept/decline/tentative from email."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import fetch_full_message, get_imap_connection
from app.mail.parsers.mime_parser import parse_full_message

logger = logging.getLogger("calendar.invite")

router = APIRouter(prefix="/api/mail", tags=["calendar-invite"])


class RsvpRequest(BaseModel):
    response: str  # ACCEPTED, DECLINED, TENTATIVE


async def _get_imap(request: Request, username: str):
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    return await get_imap_connection(login_user, password)


@router.post("/message/{folder}/{uid}/rsvp")
async def rsvp_calendar_invite(
    folder: str,
    uid: int,
    body: RsvpRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Accept, decline or tentatively accept a calendar invitation."""
    if body.response not in ("ACCEPTED", "DECLINED", "TENTATIVE"):
        raise HTTPException(status_code=400, detail="response must be ACCEPTED, DECLINED or TENTATIVE")

    imap = await _get_imap(request, username)
    try:
        raw = await fetch_full_message(imap, folder, uid)
        if not raw:
            raise HTTPException(status_code=404, detail="Message not found")

        normalized = parse_full_message(raw["raw_email"], uid=raw["uid"], flags=raw["flags"])
        if not normalized.calendar_invite:
            raise HTTPException(status_code=400, detail="This message does not contain a calendar invitation")

        invite = normalized.calendar_invite

        # 1. Save event to user's calendar
        event_saved = await _save_event_to_calendar(request, username, invite, body.response)

        # 2. Send RSVP reply email to organizer
        reply_sent = await _send_rsvp_reply(request, username, invite, body.response)

        return {
            "status": "ok",
            "response": body.response,
            "event_saved": event_saved,
            "reply_sent": reply_sent,
            "summary": invite.summary,
        }
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


async def _save_event_to_calendar(request, username: str, invite, response: str) -> bool:
    """Save the invitation event to the user's PostgreSQL calendar."""
    try:
        from app.calendar.schemas import CalendarCreate, EventCreate
        from app.calendar.service import CalendarService
        

        pool = request.app.state.db_pool
        svc = CalendarService()

        # Check if event already exists by external_uid
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                """SELECT e.id FROM events e
                   JOIN calendars c ON e.calendar_id = c.id
                   WHERE c.owner_email = $1 AND e.external_uid = $2""",
                username, invite.event_uid,
            )
            if existing:
                status_map = {"ACCEPTED": "CONFIRMED", "TENTATIVE": "TENTATIVE", "DECLINED": "CANCELLED"}
                await conn.execute(
                    "UPDATE events SET status = $1 WHERE id = $2",
                    status_map.get(response, "CONFIRMED"), existing["id"],
                )
                logger.info(f"Event updated: {invite.summary} for {username} ({response})")
                return True

        # Get or create default calendar
        calendars = await svc.list_calendars(pool, username)
        if not calendars:
            cal = await svc.create_calendar(pool, username, CalendarCreate(name="Mi Calendario", color="#0078d4"))
            calendar_id = cal.id
        else:
            calendar_id = calendars[0].id

        from datetime import datetime as dt_cls

        # Parse ISO dates from ICS
        def _parse_dt(s):
            if not s:
                return dt_cls.now()
            try:
                return dt_cls.fromisoformat(s.replace("Z", "+00:00"))
            except Exception:
                return dt_cls.now()

        attendees_list = [a["email"] for a in invite.attendees]
        event_data = EventCreate(
            calendar_id=calendar_id,
            summary=invite.summary,
            dtstart=_parse_dt(invite.dtstart),
            dtend=_parse_dt(invite.dtend) if invite.dtend else _parse_dt(invite.dtstart),
            location=invite.location,
            description=invite.description or f"Organizado por: {invite.organizer_name or invite.organizer}",
            attendees=attendees_list,
        )

        event = await svc.create_event(pool, username, event_data)

        # Store external_uid for dedup
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE events SET external_uid = $1 WHERE id = $2",
                invite.event_uid, event.id,
            )

        logger.info(f"Event saved: {invite.summary} for {username} ({response})")
        return True
    except Exception as e:
        logger.error(f"Failed to save event: {e}", exc_info=True)
        return False


async def _send_rsvp_reply(request, username: str, invite, response: str) -> bool:
    """Send iCalendar REPLY email to organizer via SMTP."""
    try:
        from datetime import datetime
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.utils import formatdate, make_msgid

        import aiosmtplib
        import vobject

        from app.config import get_settings
        from app.core.session import get_user_password

        settings = get_settings()
        password = await get_user_password(request, username)

        # Build REPLY ICS
        cal = vobject.iCalendar()
        cal.add("method").value = "REPLY"
        cal.add("prodid").value = "-//Maquita Webmail//NONSGML v1.0//EN"

        vevent = vobject.newFromBehavior("vevent")
        vevent.add("uid").value = invite.event_uid
        vevent.add("summary").value = invite.summary

        if invite.dtstart:
            try:
                dt = datetime.fromisoformat(invite.dtstart.replace("Z", "+00:00"))
                vevent.add("dtstart").value = dt
            except Exception:
                pass
        if invite.dtend:
            try:
                dt = datetime.fromisoformat(invite.dtend.replace("Z", "+00:00"))
                vevent.add("dtend").value = dt
            except Exception:
                pass

        if invite.organizer:
            org = vevent.add("organizer")
            org.value = f"mailto:{invite.organizer}"
            if invite.organizer_name:
                org.params["CN"] = [invite.organizer_name]

        att = vevent.add("attendee")
        att.value = f"mailto:{username}"
        att.params["PARTSTAT"] = [response]
        att.params["ROLE"] = ["REQ-PARTICIPANT"]

        cal.add(vevent)
        ics_reply = cal.serialize()

        # Build email
        response_labels = {"ACCEPTED": "Aceptada", "DECLINED": "Rechazada", "TENTATIVE": "Tentativa"}
        label = response_labels.get(response, response)

        msg = MIMEMultipart("mixed")
        msg["From"] = username
        msg["To"] = invite.organizer
        msg["Subject"] = f"{label}: {invite.summary}"
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=settings.mail_domain)

        text_body = f"La invitacion '{invite.summary}' ha sido {label.lower()} por {username}."
        msg.attach(MIMEText(text_body, "plain", "utf-8"))

        ics_part = MIMEText(ics_reply, "calendar", "utf-8")
        ics_part.set_param("method", "REPLY")
        msg.attach(ics_part)

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=username,
            password=password,
            start_tls=True,
            recipients=[invite.organizer],
        )
        logger.info(f"RSVP sent to {invite.organizer} for '{invite.summary}' ({response})")
        return True
    except Exception as e:
        logger.error(f"Failed to send RSVP: {e}")
        return False
