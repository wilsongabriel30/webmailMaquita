from app.mail.errors import CredencialIMAPInvalida
import aioimaplib
import asyncio
import email
import email.policy
import email.utils
import re
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings


def _decode_lines(lines) -> list[str]:
    """Decode IMAP response lines (may be bytes, bytearray, or str)."""
    result = []
    for line in lines:
        if isinstance(line, (bytes, bytearray)):
            result.append(line.decode("utf-8", errors="replace"))
        elif isinstance(line, str):
            result.append(line)
    return result


async def get_imap_connection(username: str, password: str) -> aioimaplib.IMAP4:
    """Create an authenticated IMAP connection for a user."""
    settings = get_settings()
    imap = aioimaplib.IMAP4(host=settings.imap_host, port=settings.imap_port, timeout=30)
    await imap.wait_hello_from_server()
    resp = await imap.login(username, password)
    if resp.result != "OK":
        raise CredencialIMAPInvalida("IMAP login failed")
    return imap


async def list_folders(imap: aioimaplib.IMAP4) -> list[dict]:
    """List all IMAP folders with unseen counts."""
    resp = await imap.list('""', "*")
    if resp.result != "OK":
        return []

    folders = []
    for line in _decode_lines(resp.lines):
        if not line or line == "LIST completed.":
            continue
        # Parse: (\Flags) "delimiter" "name"
        match = re.match(r'\(([^)]*)\)\s+"([^"]+)"\s+"?([^"]*)"?', line)
        if not match:
            match = re.match(r'\(([^)]*)\)\s+"([^"]+)"\s+(.+)', line)
        if match:
            flags_str, delimiter, name = match.groups()
            name = name.strip('"').strip()
            if not name:
                continue

            # Get unseen count
            unseen = 0
            try:
                status_resp = await imap.status(name, "(UNSEEN MESSAGES)")
                if status_resp.result == "OK":
                    for sline in _decode_lines(status_resp.lines):
                        m = re.search(r"UNSEEN\s+(\d+)", sline)
                        if m:
                            unseen = int(m.group(1))
            except Exception:
                pass

            flags = [f.strip() for f in flags_str.split("\\") if f.strip()]
            folder_type = _detect_folder_type(name, flags)

            folders.append({
                "name": name,
                "delimiter": delimiter,
                "flags": flags,
                "type": folder_type,
                "unseen": unseen,
            })

    return folders


def _detect_folder_type(name: str, flags: list[str]) -> str:
    name_lower = name.lower()
    if name_lower == "inbox":
        return "inbox"
    if "Sent" in flags or name_lower in ("sent", "sent messages", "sent items"):
        return "sent"
    if "Drafts" in flags or name_lower in ("drafts", "draft"):
        return "drafts"
    if "Trash" in flags or name_lower in ("trash", "deleted items", "deleted messages"):
        return "trash"
    if "Junk" in flags or name_lower in ("junk", "spam", "junk e-mail"):
        return "junk"
    if "Archive" in flags or name_lower == "archive":
        return "archive"
    return "folder"


async def list_messages(
    imap: aioimaplib.IMAP4,
    folder: str = "INBOX",
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """List messages in a folder with pagination (newest first)."""
    resp = await imap.select(folder)
    if resp.result != "OK":
        return {"messages": [], "total": 0, "page": page, "per_page": per_page}

    # Get total count
    total = 0
    for line in _decode_lines(resp.lines):
        m = re.search(r"(\d+)\s+EXISTS", line)
        if m:
            total = int(m.group(1))

    if total == 0:
        return {"messages": [], "total": 0, "page": page, "per_page": per_page}

    # Calculate range (newest first)
    end = total - (page - 1) * per_page
    start = max(1, end - per_page + 1)
    if end < 1:
        return {"messages": [], "total": total, "page": page, "per_page": per_page}

    # Fetch headers
    seq_range = f"{start}:{end}"
    fetch_resp = await imap.fetch(seq_range, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)] RFC822.SIZE)")
    if fetch_resp.result != "OK":
        return {"messages": [], "total": total, "page": page, "per_page": per_page}

    messages = _parse_fetch_response(_decode_lines(fetch_resp.lines))
    messages.reverse()  # newest first

    return {"messages": messages, "total": total, "page": page, "per_page": per_page}


def _parse_fetch_response(lines: list[str]) -> list[dict]:
    """Parse IMAP FETCH response lines into message dicts.

    aioimaplib returns lines in groups of 3:
      [0] 'N FETCH (FLAGS (\\Seen) RFC822.SIZE 1234 BODY[...] {size})'
      [1] 'From: ...\r\nTo: ...\r\nSubject: ...\r\n\r\n'  (header data)
      [2] ')'
    """
    messages = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Match FETCH line: "N FETCH (FLAGS ..."
        m = re.match(r"(\d+)\s+FETCH\s+\(", line)
        if m:
            seq = int(m.group(1))
            flags = []
            size = 0

            flags_m = re.search(r"FLAGS\s+\(([^)]*)\)", line)
            if flags_m:
                flags = flags_m.group(1).split()

            size_m = re.search(r"RFC822\.SIZE\s+(\d+)", line)
            if size_m:
                size = int(size_m.group(1))

            # Next line should be header data
            header_data = ""
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if not re.match(r"\d+\s+FETCH", next_line) and next_line != ")":
                    header_data = next_line
                    i += 1  # skip header line

            if header_data:
                messages.append(_build_message_dict(seq, flags, size, header_data))

        i += 1

    return messages


def _build_message_dict(seq: int, flags: list[str], size: int, raw_headers: str) -> dict:
    msg = email.message_from_string(raw_headers, policy=email.policy.default)
    date_str = msg.get("Date", "")
    date_parsed = None
    if date_str:
        try:
            date_parsed = email.utils.parsedate_to_datetime(date_str).isoformat()
        except Exception:
            date_parsed = date_str

    return {
        "seq": seq,
        "message_id": msg.get("Message-ID", ""),
        "from": msg.get("From", ""),
        "to": msg.get("To", ""),
        "subject": msg.get("Subject", "(No Subject)"),
        "date": date_parsed,
        "size": size,
        "flags": flags,
        "seen": "\\Seen" in flags,
        "flagged": "\\Flagged" in flags,
    }


async def get_message(imap: aioimaplib.IMAP4, folder: str, seq: int) -> dict | None:
    """Fetch a full message by sequence number."""
    resp = await imap.select(folder)
    if resp.result != "OK":
        return None

    fetch_resp = await imap.fetch(str(seq), "(FLAGS RFC822)")
    if fetch_resp.result != "OK":
        return None

    # Parse aioimaplib response: [FETCH_LINE, RAW_EMAIL_DATA, ")", ...]
    lines = _decode_lines(fetch_resp.lines)
    raw_email = ""
    flags = []

    for i, line in enumerate(lines):
        m = re.match(r"\d+\s+FETCH\s+\(", line)
        if m:
            flags_m = re.search(r"FLAGS\s+\(([^)]*)\)", line)
            flags = flags_m.group(1).split() if flags_m else []
            # Next line is the raw email data
            if i + 1 < len(lines):
                raw_email = lines[i + 1]
            break

    if not raw_email:
        return None

    msg = email.message_from_string(raw_email, policy=email.policy.default)

    # Extract body parts
    text_body = ""
    html_body = ""
    attachments = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in disposition:
                attachments.append({
                    "filename": part.get_filename() or "unnamed",
                    "content_type": content_type,
                    "size": len(part.get_payload(decode=True) or b""),
                })
            elif content_type == "text/plain" and not text_body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    text_body = payload.decode(charset, errors="replace")
            elif content_type == "text/html" and not html_body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_body = payload.decode(charset, errors="replace")
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                html_body = decoded
            else:
                text_body = decoded

    date_str = msg.get("Date", "")
    date_parsed = None
    if date_str:
        try:
            date_parsed = email.utils.parsedate_to_datetime(date_str).isoformat()
        except Exception:
            date_parsed = date_str

    return {
        "seq": seq,
        "message_id": msg.get("Message-ID", ""),
        "from": msg.get("From", ""),
        "to": msg.get("To", ""),
        "cc": msg.get("Cc", ""),
        "subject": msg.get("Subject", "(No Subject)"),
        "date": date_parsed,
        "text_body": text_body,
        "html_body": html_body,
        "attachments": attachments,
        "flags": flags if "flags" in dir() else [],
        "seen": True,
    }


async def move_message(imap: aioimaplib.IMAP4, folder: str, seq: int, dest_folder: str) -> bool:
    """Move a message to another folder."""
    resp = await imap.select(folder)
    if resp.result != "OK":
        return False

    # Copy then delete
    copy_resp = await imap.copy(str(seq), dest_folder)
    if copy_resp.result != "OK":
        return False

    await imap.store(str(seq), "+FLAGS", "(\\Deleted)")
    await imap.expunge()
    return True


async def set_flags(imap: aioimaplib.IMAP4, folder: str, seq: int, flags: str, add: bool = True) -> bool:
    """Add or remove flags on a message."""
    resp = await imap.select(folder)
    if resp.result != "OK":
        return False

    action = "+FLAGS" if add else "-FLAGS"
    store_resp = await imap.store(str(seq), action, f"({flags})")
    return store_resp.result == "OK"


async def delete_message(imap: aioimaplib.IMAP4, folder: str, seq: int) -> bool:
    """Mark message as deleted and expunge."""
    resp = await imap.select(folder)
    if resp.result != "OK":
        return False

    await imap.store(str(seq), "+FLAGS", "(\\Deleted)")
    await imap.expunge()
    return True
