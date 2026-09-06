"""MIME parser — converts raw email to NormalizedMessage.

Chain: raw email string -> NormalizedMessage (dataclass)
"""

import email
import email.policy
import email.utils
import re
from dataclasses import dataclass, field


@dataclass
class AttachmentInfo:
    filename: str
    content_type: str
    size: int
    part_number: str
    is_inline: bool = False
    cid: str = ""


@dataclass
class CalendarInviteInfo:
    """Parsed calendar invitation from text/calendar MIME part."""

    method: str = ""  # REQUEST, REPLY, CANCEL
    event_uid: str = ""
    summary: str = ""
    dtstart: str = ""
    dtend: str = ""
    location: str = ""
    organizer: str = ""
    organizer_name: str = ""
    description: str = ""
    raw_ics: str = ""
    attendees: list = field(default_factory=list)  # [{email, name, role, partstat}]


@dataclass
class NormalizedMessage:
    """Intermediate representation between raw IMAP and API response."""

    uid: int = 0
    message_id: str = ""
    from_addr: str = ""
    to_addr: str = ""
    cc_addr: str = ""
    subject: str = "(No Subject)"
    date: str | None = None
    date_raw: str = ""
    size: int = 0
    flags: list[str] = field(default_factory=list)
    seen: bool = False
    flagged: bool = False
    text_body: str = ""
    html_body: str = ""
    snippet: str = ""
    attachments: list[AttachmentInfo] = field(default_factory=list)
    has_attachments: bool = False
    cid_map: dict = field(default_factory=dict)
    calendar_invite: CalendarInviteInfo | None = None
    references: str = ""
    in_reply_to: str = ""
    importance: str = "normal"


def parse_headers(
    raw_headers: str, uid: int = 0, flags: list[str] | None = None, size: int = 0
) -> NormalizedMessage:
    """Parse raw headers into a NormalizedMessage (without body)."""
    msg = email.message_from_string(raw_headers, policy=email.policy.default)
    flags = flags or []

    date_str = msg.get("Date", "")
    date_parsed = None
    if date_str:
        try:
            date_parsed = email.utils.parsedate_to_datetime(date_str).isoformat()
        except Exception:
            date_parsed = date_str

    return NormalizedMessage(
        uid=uid,
        message_id=msg.get("Message-ID", "") or "",
        from_addr=msg.get("From", "") or "",
        to_addr=msg.get("To", "") or "",
        cc_addr=msg.get("Cc", "") or "",
        subject=msg.get("Subject", "") or "(No Subject)",
        date=date_parsed,
        date_raw=date_str,
        size=size,
        flags=flags,
        seen="\\Seen" in flags,
        flagged="\\Flagged" in flags,
        references=msg.get("References", "") or "",
        in_reply_to=msg.get("In-Reply-To", "") or "",
        importance=_detect_importance(msg),
    )


def parse_full_message(
    raw_email: str, uid: int = 0, flags: list[str] | None = None
) -> NormalizedMessage:
    """Parse a complete raw email into NormalizedMessage with body and attachments."""
    msg = email.message_from_string(raw_email, policy=email.policy.default)
    flags = flags or []

    date_str = msg.get("Date", "")
    date_parsed = None
    if date_str:
        try:
            date_parsed = email.utils.parsedate_to_datetime(date_str).isoformat()
        except Exception:
            date_parsed = date_str

    text_body, html_body, attachments, cid_map, calendar_invite = _extract_parts(msg)
    snippet = _generate_snippet(text_body, html_body)

    return NormalizedMessage(
        uid=uid,
        message_id=msg.get("Message-ID", "") or "",
        from_addr=msg.get("From", "") or "",
        to_addr=msg.get("To", "") or "",
        cc_addr=msg.get("Cc", "") or "",
        subject=msg.get("Subject", "") or "(No Subject)",
        date=date_parsed,
        date_raw=date_str,
        size=len(raw_email),
        flags=flags,
        seen="\\Seen" in flags,
        flagged="\\Flagged" in flags,
        text_body=text_body,
        html_body=html_body,
        snippet=snippet,
        attachments=attachments,
        has_attachments=any(not a.is_inline for a in attachments),
        cid_map=cid_map,
        calendar_invite=calendar_invite,
        references=msg.get("References", "") or "",
        in_reply_to=msg.get("In-Reply-To", "") or "",
        importance=_detect_importance(msg),
    )


def _extract_parts(
    msg, part_prefix: str = ""
) -> tuple[str, str, list[AttachmentInfo], dict[str, str]]:
    text_body = ""
    html_body = ""
    attachments = []
    cid_map: dict[str, str] = {}
    calendar_invite: CalendarInviteInfo | None = None

    if msg.is_multipart():
        for idx, part in enumerate(msg.get_payload(), 1):
            part_num = f"{part_prefix}{idx}" if part_prefix else str(idx)
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            cid = (part.get("Content-ID", "") or "").strip("<>")

            if "attachment" in disposition:
                # Una invitación text/calendar puede venir como adjunto
                # (Outlook/Google y nuestro propio invite.ics): parsearla
                # igualmente para mostrar el banner RSVP.
                if content_type == "text/calendar" and not calendar_invite:
                    try:
                        calendar_invite = _parse_ics_part(part)
                    except Exception:
                        pass
                payload = part.get_payload(decode=True)
                attachments.append(
                    AttachmentInfo(
                        filename=part.get_filename() or "unnamed",
                        content_type=content_type,
                        size=len(payload) if payload else 0,
                        part_number=part_num,
                        is_inline=False,
                        cid=cid,
                    )
                )
            elif part.is_multipart():
                t, h, a, cm, ci = _extract_parts(part, part_num + ".")
                if not text_body:
                    text_body = t
                if not html_body:
                    html_body = h
                attachments.extend(a)
                cid_map.update(cm)
                if ci and not calendar_invite:
                    calendar_invite = ci
            elif content_type == "text/calendar":
                try:
                    calendar_invite = _parse_ics_part(part)
                except Exception:
                    pass  # Si falla el parsing, ignorar silenciosamente
            elif content_type == "text/plain" and not text_body:
                text_body = _decode_payload(part)
            elif content_type == "text/html" and not html_body:
                html_body = _decode_payload(part)
            elif cid or "inline" in disposition:
                payload = part.get_payload(decode=True)
                attachments.append(
                    AttachmentInfo(
                        filename=part.get_filename() or f"inline_{part_num}",
                        content_type=content_type,
                        size=len(payload) if payload else 0,
                        part_number=part_num,
                        is_inline=True,
                        cid=cid,
                    )
                )
                if cid and payload:
                    import base64

                    b64 = base64.b64encode(payload).decode("ascii")
                    cid_map[cid] = f"data:{content_type};base64,{b64}"
            elif content_type.startswith(("image/", "application/")):
                payload = part.get_payload(decode=True)
                attachments.append(
                    AttachmentInfo(
                        filename=part.get_filename() or f"attachment_{part_num}",
                        content_type=content_type,
                        size=len(payload) if payload else 0,
                        part_number=part_num,
                    )
                )
    else:
        content_type = msg.get_content_type()
        if content_type == "text/calendar":
            try:
                calendar_invite = _parse_ics_part(msg)
            except Exception:
                pass
        elif content_type == "text/html":
            html_body = _decode_payload(msg)
        else:
            text_body = _decode_payload(msg)

    return text_body, html_body, attachments, cid_map, calendar_invite


def _decode_payload(part) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    charset_map = {"windows-1252": "cp1252", "iso-8859-1": "latin-1", "ascii": "utf-8"}
    charset = charset_map.get(charset.lower(), charset)
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")


def _generate_snippet(text_body: str, html_body: str, max_length: int = 150) -> str:
    source = text_body
    if not source and html_body:
        source = re.sub(r"<[^>]+>", " ", html_body)
        source = re.sub(r"&\w+;", " ", source)
    if not source:
        return ""
    source = re.sub(r"\s+", " ", source).strip()
    if len(source) > max_length:
        return source[:max_length].rsplit(" ", 1)[0] + "..."
    return source


def _detect_importance(msg) -> str:
    x_priority = msg.get("X-Priority", "")
    if x_priority:
        try:
            p = int(x_priority.strip().split()[0])
            if p <= 2:
                return "high"
            elif p >= 4:
                return "low"
        except (ValueError, IndexError):
            pass
    importance = (msg.get("Importance", "") or "").lower().strip()
    if importance in ("high", "low"):
        return importance
    return "normal"


def _parse_ics_part(part) -> CalendarInviteInfo | None:
    """Parse a text/calendar MIME part into CalendarInviteInfo."""
    import vobject

    raw_ics = _decode_payload(part)
    if not raw_ics:
        return None

    cal = vobject.readOne(raw_ics)
    method = ""
    if hasattr(cal, "method"):
        method = cal.method.value.upper()

    vevent = None
    for child in cal.getChildren():
        if child.name == "VEVENT":
            vevent = child
            break

    if not vevent:
        return None

    # Extract basic fields
    summary = vevent.summary.value if hasattr(vevent, "summary") else ""
    event_uid = vevent.uid.value if hasattr(vevent, "uid") else ""
    location = vevent.location.value if hasattr(vevent, "location") else ""
    description = vevent.description.value if hasattr(vevent, "description") else ""

    # Dates
    dtstart = ""
    dtend = ""
    if hasattr(vevent, "dtstart"):
        dt = vevent.dtstart.value
        dtstart = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
    if hasattr(vevent, "dtend"):
        dt = vevent.dtend.value
        dtend = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)

    # Organizer
    organizer = ""
    organizer_name = ""
    if hasattr(vevent, "organizer"):
        org = vevent.organizer
        organizer = str(org.value).replace("mailto:", "").replace("MAILTO:", "")
        organizer_name = (
            org.params.get("CN", [""])[0]
            if hasattr(org, "params") and org.params
            else ""
        )

    # Attendees
    attendees = []
    if hasattr(vevent, "attendee_list"):
        for att in vevent.attendee_list:
            email = str(att.value).replace("mailto:", "").replace("MAILTO:", "")
            name = (
                att.params.get("CN", [""])[0]
                if hasattr(att, "params") and att.params
                else ""
            )
            role = (
                att.params.get("ROLE", ["REQ-PARTICIPANT"])[0]
                if hasattr(att, "params") and att.params
                else "REQ-PARTICIPANT"
            )
            partstat = (
                att.params.get("PARTSTAT", ["NEEDS-ACTION"])[0]
                if hasattr(att, "params") and att.params
                else "NEEDS-ACTION"
            )
            attendees.append(
                {
                    "email": email,
                    "name": name,
                    "role": role,
                    "partstat": partstat,
                }
            )

    return CalendarInviteInfo(
        method=method,
        event_uid=event_uid,
        summary=summary,
        dtstart=dtstart,
        dtend=dtend,
        location=location,
        organizer=organizer,
        organizer_name=organizer_name,
        attendees=attendees,
        description=description,
        raw_ics=raw_ics,
    )
