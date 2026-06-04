"""Message service — list and read messages with parsing."""
import re
from app.mail.clients.imap_client import (
    list_message_uids, fetch_message_headers, fetch_full_message,
)
from app.mail.parsers.mime_parser import parse_headers, parse_full_message
from app.mail.parsers.html_sanitizer import sanitize_html
from app.mail.rendering.policy import apply_render_policy
from app.config import get_settings


async def list_messages(
    imap,
    folder: str = "INBOX",
    page: int = 1,
    per_page: int = 50,
    search_query: str = "",
    redis=None,
    username: str = "",
) -> dict:
    """List messages with snippets, newest first."""
    uid_result = await list_message_uids(imap, folder, page, per_page, search_query, redis=redis, username=username)

    # If folder select failed, uid_result will have folder_error flag
    if uid_result.get("folder_error"):
        return None  # Signal to router that folder does not exist

    if not uid_result["uids"]:
        return {
            "messages": [],
            "total": uid_result["total"],
            "page": page,
            "per_page": per_page,
        }

    raw_headers = await fetch_message_headers(imap, uid_result["uids"])

    messages = []
    for raw in raw_headers:
        normalized = parse_headers(
            raw["raw_headers"],
            uid=raw["uid"],
            flags=raw["flags"],
            size=raw["size"],
        )
        summary = _summary_from_normalized(normalized, folder)
        # Use snippet from IMAP fetch if available
        if raw.get("snippet"):
            summary["snippet"] = raw["snippet"]
        # Use has_attachments from BODYSTRUCTURE if available
        if raw.get("has_attachments"):
            summary["has_attachments"] = True
        messages.append(summary)

    # Preserve UID order (newest first)
    uid_order = {u: i for i, u in enumerate(uid_result["uids"])}
    messages.sort(key=lambda m: uid_order.get(m["uid"], 999999))

    return {
        "messages": messages,
        "total": uid_result["total"],
        "page": page,
        "per_page": per_page,
    }


async def get_message(
    imap,
    folder: str,
    uid: int,
    block_remote_images: bool = True,
) -> dict | None:
    """Get full message by UID with sanitized HTML."""
    raw = await fetch_full_message(imap, folder, uid)
    if not raw:
        return None

    normalized = parse_full_message(
        raw["raw_email"],
        uid=raw["uid"],
        flags=raw["flags"],
    )

    # Auto-allow images from trusted Maquita domains
    _settings = get_settings()
    _TRUSTED_DOMAINS = {"ejemplo.com", "maquitaturismo.com", _settings.mail_domain}
    sender = normalized.from_addr or ""
    sender_match = re.search(r"@([\w.-]+)", sender)
    if sender_match and sender_match.group(1).lower() in _TRUSTED_DOMAINS:
        block_remote_images = False

    # Sanitize HTML
    safe_html = ""
    render_info = {"has_remote_images": False, "blocked_image_count": 0}
    if normalized.html_body:
        sanitized = sanitize_html(normalized.html_body)
        render_result = apply_render_policy(sanitized, block_remote_images=block_remote_images, cid_map=normalized.cid_map)
        safe_html = render_result["html"]
        render_info = render_result

    return {
        "uid": normalized.uid,
        "folder": folder,
        "message_id": normalized.message_id,
        "thread_id": _compute_thread_id(normalized),
        "from": normalized.from_addr,
        "to": normalized.to_addr,
        "cc": normalized.cc_addr,
        "subject": normalized.subject,
        "date": normalized.date,
        "size": normalized.size,
        "flags": normalized.flags,
        "seen": True,
        "flagged": normalized.flagged,
        "text_body": normalized.text_body,
        "html_body": safe_html,
        "attachments": [
            {
                "filename": a.filename,
                "content_type": a.content_type,
                "size": a.size,
                "part_number": a.part_number,
                "is_inline": a.is_inline,
            }
            for a in normalized.attachments
        ],
        "has_attachments": normalized.has_attachments,
        "importance": normalized.importance,
        "has_remote_images": render_info.get("has_remote_images", False),
        "blocked_image_count": render_info.get("blocked_image_count", 0),
        "snippet": normalized.snippet,
        "references": normalized.references,
        "in_reply_to": normalized.in_reply_to,
        "calendar_invite": _serialize_calendar_invite(normalized.calendar_invite),
    }


def _summary_from_normalized(n, folder: str) -> dict:
    """Convert NormalizedMessage to MessageSummary dict."""
    return {
        "uid": n.uid,
        "folder": folder,
        "message_id": n.message_id,
        "thread_id": _compute_thread_id(n),
        "from": n.from_addr,
        "to": n.to_addr,
        "subject": n.subject,
        "date": n.date,
        "size": n.size,
        "flags": n.flags,
        "seen": n.seen,
        "flagged": n.flagged,
        "snippet": n.snippet if n.snippet else "",
        "has_attachments": n.has_attachments,
        "importance": n.importance,
    }


def _compute_thread_id(n) -> str:
    """Derive thread_id from References/In-Reply-To or subject fallback."""
    if n.references:
        # First message-id in References is the thread root
        ids = n.references.strip().split()
        if ids:
            return ids[0].strip("<>")
    if n.in_reply_to:
        return n.in_reply_to.strip("<>")
    # Fallback: normalized subject
    import re
    subj = re.sub(r"^(Re|Fwd|Fw)\s*:\s*", "", n.subject, flags=re.IGNORECASE).strip()
    if subj:
        import hashlib
        return hashlib.md5(subj.lower().encode()).hexdigest()[:12]
    return ""


def _serialize_calendar_invite(invite) -> dict | None:
    """Serialize CalendarInviteInfo to dict for API response."""
    if not invite:
        return None
    return {
        "method": invite.method,
        "event_uid": invite.event_uid,
        "summary": invite.summary,
        "dtstart": invite.dtstart,
        "dtend": invite.dtend,
        "location": invite.location,
        "organizer": invite.organizer,
        "organizer_name": invite.organizer_name,
        "attendees": invite.attendees,
        "description": invite.description,
    }
