"""iCalendar utilities: build, parse, uid generation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from icalendar import Calendar, Event, vDatetime

from app.config import get_settings


def generate_uid() -> str:
    """Generate a unique iCal UID."""
    return f"{uuid.uuid4()}@{get_settings().mail_domain}"


def build_vcalendar(event_data: dict) -> str:
    """Build a VCALENDAR string from event data dict.

    Expected keys: uid, summary, description, location, dtstart, dtend,
    all_day, rrule, status, transparency, timezone, attendees.
    """
    cal = Calendar()
    cal.add("prodid", "-//Maquita Webmail//Calendar//ES")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    _method = event_data.get("method")
    if _method:
        cal.add("method", _method)

    ev = Event()
    _organizer = event_data.get("organizer")
    if _organizer:
        from icalendar import vCalAddress

        org = vCalAddress(f"mailto:{_organizer}")
        if event_data.get("organizer_name"):
            org.params["CN"] = event_data["organizer_name"]
        ev.add("organizer", org, encode=0)
    ev.add("uid", event_data["uid"])
    ev.add("summary", event_data.get("summary", ""))
    ev.add("description", event_data.get("description", ""))
    ev.add("location", event_data.get("location", ""))
    ev.add("status", event_data.get("status", "CONFIRMED"))
    ev.add("transp", event_data.get("transparency", "OPAQUE"))
    ev.add("dtstamp", datetime.now(timezone.utc))

    dtstart = event_data["dtstart"]
    dtend = event_data["dtend"]
    if isinstance(dtstart, str):
        dtstart = datetime.fromisoformat(dtstart)
    if isinstance(dtend, str):
        dtend = datetime.fromisoformat(dtend)

    if event_data.get("all_day"):
        ev.add("dtstart", dtstart.date())
        ev.add("dtend", dtend.date())
    else:
        ev.add("dtstart", dtstart)
        ev.add("dtend", dtend)

    rrule = event_data.get("rrule", "")
    if rrule:
        # Parse RRULE string into dict for icalendar
        parts = {}
        for part in rrule.replace("RRULE:", "").split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                parts[k] = v
        ev.add("rrule", parts)

    for att in event_data.get("attendees", []):
        if isinstance(att, dict) and att.get("email"):
            from icalendar import vCalAddress, vText

            attendee = vCalAddress(f"mailto:{att['email']}")
            role = att.get("role", "REQ-PARTICIPANT")
            attendee.params["ROLE"] = role
            attendee.params["PARTSTAT"] = att.get("status", "NEEDS-ACTION")
            if att.get("name"):
                attendee.params["CN"] = att["name"]
            ev.add("attendee", attendee, encode=0)

    # Reminders / VALARM
    for rem in event_data.get("reminders", []):
        from datetime import timedelta

        from icalendar import Alarm

        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", event_data.get("summary", "Recordatorio"))
        minutes = rem.get("minutes", 15) if isinstance(rem, dict) else 15
        alarm.add("trigger", timedelta(minutes=-minutes))
        ev.add_component(alarm)

    cal.add_component(ev)
    return cal.to_ical().decode("utf-8")


def parse_vcalendar(ical_str: str) -> dict:
    """Parse an iCalendar string back into a dict with event fields."""
    cal = Calendar.from_ical(ical_str)
    for component in cal.walk():
        if component.name == "VEVENT":
            dtstart = component.get("dtstart")
            dtend = component.get("dtend")
            return {
                "uid": str(component.get("uid", "")),
                "summary": str(component.get("summary", "")),
                "description": str(component.get("description", "")),
                "location": str(component.get("location", "")),
                "dtstart": dtstart.dt if dtstart else None,
                "dtend": dtend.dt if dtend else None,
                "status": str(component.get("status", "CONFIRMED")),
                "transparency": str(component.get("transp", "OPAQUE")),
                "rrule": str(component.get("rrule", "")),
            }
    return {}
