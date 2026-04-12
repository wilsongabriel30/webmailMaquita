"""Pure IMAP client — UID-based operations only.

All operations use IMAP UID commands for stable message identification.
No business logic: the service layer orchestrates with parsers.
"""
import aioimaplib
import re

from app.config import get_settings


def _quote_folder(name: str) -> str:
    """Quote IMAP folder name if it contains spaces or special chars."""
    if ' ' in name or '"' in name or '(' in name or ')' in name:
        return '"' + name.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return name


def _decode_lines(lines) -> list[str]:
    result = []
    for line in lines:
        if isinstance(line, (bytes, bytearray)):
            result.append(line.decode("utf-8", errors="replace"))
        elif isinstance(line, str):
            result.append(line)
    return result


async def get_imap_connection(username: str, password: str) -> aioimaplib.IMAP4:
    settings = get_settings()
    imap = aioimaplib.IMAP4(host=settings.imap_host, port=settings.imap_port, timeout=30)
    await imap.wait_hello_from_server()
    resp = await imap.login(username, password)
    if resp.result != "OK":
        raise ConnectionError("IMAP login failed")
    return imap


async def list_folders(imap: aioimaplib.IMAP4) -> list[dict]:
    """List all IMAP folders with unseen counts."""
    resp = await imap.list('""', "*")
    if resp.result != "OK":
        return []

    folders = []
    for line in _decode_lines(resp.lines):
        if not line or line.endswith("completed."):
            continue
        match = re.match(r'\(([^)]*)\)\s+"([^"]+)"\s+"?([^"]*)"?', line)
        if not match:
            match = re.match(r'\(([^)]*)\)\s+"([^"]+)"\s+(.+)', line)
        if match:
            flags_str, delimiter, name = match.groups()
            name = name.strip('"').strip()
            if not name:
                continue
            unseen = 0
            try:
                status_resp = await imap.status(_quote_folder(name), "(UNSEEN MESSAGES)")
                if status_resp.result == "OK":
                    for sline in _decode_lines(status_resp.lines):
                        m = re.search(r"UNSEEN\s+(\d+)", sline)
                        if m:
                            unseen = int(m.group(1))
            except Exception:
                pass
            flags = [f.strip() for f in flags_str.split("\\") if f.strip()]
            folders.append({
                "name": name,
                "delimiter": delimiter,
                "flags": flags,
                "unseen": unseen,
            })
    return folders


async def list_message_uids(
    imap: aioimaplib.IMAP4,
    folder: str = "INBOX",
    page: int = 1,
    per_page: int = 50,
    search_query: str = "",
) -> dict:
    """List message UIDs with pagination (newest first)."""
    resp = await imap.select(_quote_folder(folder))
    if resp.result != "OK":
        return {"uids": [], "total": 0, "page": page, "per_page": per_page, "folder_error": True}

    # Try SORT for server-side ordering (faster than SEARCH + client sort)
    use_sort = True
    if search_query:
        criteria = _build_search_criteria(search_query)
    else:
        criteria = ["ALL"]

    all_uids = []
    if use_sort:
        try:
            sort_resp = await imap.uid("sort", "(REVERSE DATE)", "UTF-8", *criteria)
            if sort_resp.result == "OK":
                for line in _decode_lines(sort_resp.lines):
                    line = line.strip()
                    if line and not line.endswith("completed."):
                        all_uids.extend(int(x) for x in line.split() if x.isdigit())
            else:
                use_sort = False
        except Exception:
            use_sort = False

    if not use_sort:
        search_resp = await imap.uid_search(*criteria)
        if search_resp.result != "OK":
            return {"uids": [], "total": 0, "page": page, "per_page": per_page}
        for line in _decode_lines(search_resp.lines):
            line = line.strip()
            if line and not line.endswith("completed."):
                all_uids.extend(int(x) for x in line.split() if x.isdigit())
        all_uids.sort(reverse=True)
    total = len(all_uids)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_uids = all_uids[start_idx:end_idx]

    return {"uids": page_uids, "total": total, "page": page, "per_page": per_page}


def _build_search_criteria(query: str) -> list[str]:
    from app.mail.search_advanced import parse_search_query
    return parse_search_query(query)

async def fetch_message_headers(
    imap: aioimaplib.IMAP4,
    uids: list[int],
) -> list[dict]:
    """Fetch headers, metadata, bodystructure, and text snippet for a list of UIDs."""
    if not uids:
        return []

    uid_set = ",".join(str(u) for u in uids)
    # BODYSTRUCTURE for attachment detection, BODY.PEEK[TEXT]<0.512> for snippet
    fetch_items = "(UID FLAGS RFC822.SIZE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID REFERENCES IN-REPLY-TO X-PRIORITY IMPORTANCE)])"

    fetch_resp = await imap.uid("fetch", uid_set, fetch_items)
    if fetch_resp.result != "OK":
        return []

    return _parse_uid_fetch_response(fetch_resp.lines)


def _clean_snippet(raw: str) -> str:
    """Extract a clean text snippet from raw body text."""
    if not raw:
        return ""
    # Remove IMAP fetch prefixes like "BODY[TEXT] {242}"
    text = re.sub(r"^BODY\[TEXT\](?:\s*<\d+>)?\s*\{\d+\}\s*", "", raw, flags=re.IGNORECASE)
    # Decode quoted-printable encoding (=C3=B3 -> ó, =20 -> space, etc.)
    import quopri
    try:
        text = quopri.decodestring(text.encode("utf-8", errors="replace")).decode("utf-8", errors="replace")
    except Exception:
        pass
    # Remove MIME boundaries and headers
    text = re.sub(r"--[A-Za-z0-9_=+/.-]+", "", text)
    text = re.sub(r"Content-[A-Za-z-]+:.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"charset=.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"MIME-Version:.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"boundary=.*", "", text, flags=re.IGNORECASE)
    # Remove base64 encoded blocks
    text = re.sub(r"[A-Za-z0-9+/=]{40,}", "", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common HTML entities
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"&[a-z]+;", "", text)
    # Clean whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Limit to ~200 chars
    if len(text) > 200:
        text = text[:197] + "..."
    return text


def _has_attachments_from_bodystructure(line_str: str) -> bool:
    """Check if BODYSTRUCTURE indicates attachments (multipart/mixed with >1 part)."""
    s = line_str.upper()
    # If message has BODYSTRUCTURE with "ATTACHMENT" disposition
    if "ATTACHMENT" in s:
        return True
    # multipart/mixed usually means attachments
    if "MIXED" in s and s.count("(") > 3:
        return True
    return False


def _parse_uid_fetch_response(raw_lines) -> list[dict]:
    """Parse IMAP UID FETCH response. raw_lines can be bytes or str."""
    messages = []

    # Decode all lines to strings
    lines = []
    for line in raw_lines:
        if isinstance(line, (bytes, bytearray)):
            lines.append(line.decode("utf-8", errors="replace"))
        elif isinstance(line, str):
            lines.append(line)

    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"\d+\s+FETCH\s+\(", line)
        if m:
            uid = 0
            flags = []
            size = 0
            has_attach = False

            uid_m = re.search(r"UID\s+(\d+)", line)
            if uid_m:
                uid = int(uid_m.group(1))

            flags_m = re.search(r"FLAGS\s+\(([^)]*)\)", line)
            if flags_m:
                flags = flags_m.group(1).split()

            size_m = re.search(r"RFC822\.SIZE\s+(\d+)", line)
            if size_m:
                size = int(size_m.group(1))

            # Check BODYSTRUCTURE in the FETCH line itself
            if "BODYSTRUCTURE" in line:
                has_attach = _has_attachments_from_bodystructure(line)

            # Collect subsequent data lines
            header_data = ""
            body_text = ""
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                # Next message starts
                if re.match(r"\d+\s+FETCH\s+\(", next_line):
                    break
                # Skip closing paren and completion
                if next_line.strip() == ")" or "completed" in next_line.lower():
                    j += 1
                    continue
                # Skip IMAP metadata lines like " BODY[TEXT]<0> {242}"
                if re.match(r"\s*BODY\[", next_line):
                    j += 1
                    continue
                # The first real string data is the headers
                if not header_data:
                    header_data = next_line
                else:
                    # Subsequent data is body text for snippet
                    if body_text:
                        body_text += " " + next_line
                    else:
                        body_text = next_line
                j += 1

            if uid > 0 and header_data:
                snippet = _clean_snippet(body_text) if body_text else ""
                messages.append({
                    "uid": uid,
                    "flags": flags,
                    "size": size,
                    "raw_headers": header_data,
                    "snippet": snippet,
                    "has_attachments": has_attach,
                })
            i = j
            continue
        i += 1
    return messages


async def fetch_full_message(
    imap: aioimaplib.IMAP4,
    folder: str,
    uid: int,
) -> dict | None:
    """Fetch a full message by UID. Returns raw email data."""
    resp = await imap.select(_quote_folder(folder))
    if resp.result != "OK":
        return None

    fetch_resp = await imap.uid("fetch", str(uid), "(UID FLAGS RFC822)")
    if fetch_resp.result != "OK":
        return None

    lines = _decode_lines(fetch_resp.lines)
    raw_email = ""
    flags = []
    actual_uid = 0

    for idx, line in enumerate(lines):
        m_line = re.match(r"\d+\s+FETCH\s+\(", line)
        if m_line:
            uid_m = re.search(r"UID\s+(\d+)", line)
            if uid_m:
                actual_uid = int(uid_m.group(1))
            flags_m = re.search(r"FLAGS\s+\(([^)]*)\)", line)
            if flags_m:
                flags = flags_m.group(1).split()
            if idx + 1 < len(lines):
                raw_email = lines[idx + 1]
            break

    if not raw_email:
        return None

    await imap.uid("store", str(uid), "+FLAGS", "(\\Seen)")

    return {
        "uid": actual_uid or uid,
        "flags": flags,
        "raw_email": raw_email,
    }


async def fetch_raw_message(
    imap: aioimaplib.IMAP4,
    folder: str,
    uid: int,
) -> str | None:
    """Fetch raw RFC822 message for .eml download or source view."""
    resp = await imap.select(_quote_folder(folder))
    if resp.result != "OK":
        return None

    fetch_resp = await imap.uid("fetch", str(uid), "(RFC822)")
    if fetch_resp.result != "OK":
        return None

    lines = _decode_lines(fetch_resp.lines)
    for idx, line in enumerate(lines):
        if re.match(r"\d+\s+FETCH\s+\(", line) and idx + 1 < len(lines):
            return lines[idx + 1]
    return None


async def fetch_attachment(
    imap: aioimaplib.IMAP4,
    folder: str,
    uid: int,
    part_number: str,
) -> bytes | None:
    """Fetch a specific MIME part by UID and part number.

    aioimaplib returns FETCH responses as multiple lines:
    - Line 0: IMAP header like b'9026 FETCH (UID 9036 BODY[2] {452802}'
    - Line 1: The actual attachment data (largest bytes line)
    - Line N: Closing paren b')'
    We return the largest bytes line which is the actual content.
    """
    resp = await imap.select(_quote_folder(folder))
    if resp.result != "OK":
        return None

    fetch_resp = await imap.uid("fetch", str(uid), f"(BODY.PEEK[{part_number}])")
    if fetch_resp.result != "OK":
        return None

    # Find the largest bytes line — that's the attachment data
    largest = None
    for line in fetch_resp.lines:
        if isinstance(line, (bytes, bytearray)):
            if largest is None or len(line) > len(largest):
                largest = line
    if largest is None:
        return None

    # IMAP returns attachment data as base64-encoded.
    # Try to decode; if it fails, return raw bytes.
    import base64
    try:
        return base64.b64decode(largest)
    except Exception:
        return bytes(largest)


async def uid_move_message(imap: aioimaplib.IMAP4, folder: str, uid: int, dest_folder: str) -> bool:
    resp = await imap.select(_quote_folder(folder))
    if resp.result != "OK":
        return False
    copy_resp = await imap.uid("copy", str(uid), _quote_folder(dest_folder))
    if copy_resp.result != "OK":
        return False
    await imap.uid("store", str(uid), "+FLAGS", "(\\Deleted)")
    await imap.expunge()
    return True


async def uid_set_flags(imap: aioimaplib.IMAP4, folder: str, uid: int, flags: str, add: bool = True) -> bool:
    resp = await imap.select(_quote_folder(folder))
    if resp.result != "OK":
        return False
    action = "+FLAGS" if add else "-FLAGS"
    store_resp = await imap.uid("store", str(uid), action, f"({flags})")
    return store_resp.result == "OK"


async def uid_delete_message(imap: aioimaplib.IMAP4, folder: str, uid: int) -> bool:
    resp = await imap.select(_quote_folder(folder))
    if resp.result != "OK":
        return False
    # Verify UID exists before deleting
    check = await imap.uid("fetch", str(uid), "(FLAGS)")
    if check.result != "OK":
        return False
    lines = _decode_lines(check.lines)
    uid_found = any(f"UID {uid}" in line or f"UID  {uid}" in line for line in lines if "FETCH" in line)
    if not uid_found:
        return False
    await imap.uid("store", str(uid), "+FLAGS", "(\\Deleted)")
    await imap.expunge()
    return True


async def uid_bulk_action(
    imap: aioimaplib.IMAP4,
    folder: str,
    uids: list[int],
    action: str,
    dest_folder: str = "",
) -> bool:
    """Bulk actions: delete, move, mark_read, mark_unread, flag, unflag, archive."""
    resp = await imap.select(_quote_folder(folder))
    if resp.result != "OK":
        return False

    uid_set = ",".join(str(u) for u in uids)

    if action == "delete":
        await imap.uid("store", uid_set, "+FLAGS", "(\\Deleted)")
        await imap.expunge()
    elif action == "move" and dest_folder:
        copy_resp = await imap.uid("copy", uid_set, _quote_folder(dest_folder))
        if copy_resp.result != "OK":
            return False
        await imap.uid("store", uid_set, "+FLAGS", "(\\Deleted)")
        await imap.expunge()
    elif action == "mark_read":
        await imap.uid("store", uid_set, "+FLAGS", "(\\Seen)")
    elif action == "mark_unread":
        await imap.uid("store", uid_set, "-FLAGS", "(\\Seen)")
    elif action == "flag":
        await imap.uid("store", uid_set, "+FLAGS", "(\\Flagged)")
    elif action == "unflag":
        await imap.uid("store", uid_set, "-FLAGS", "(\\Flagged)")
    elif action == "archive":
        copy_resp = await imap.uid("copy", uid_set, "Archive")
        if copy_resp.result != "OK":
            return False
        await imap.uid("store", uid_set, "+FLAGS", "(\\Deleted)")
        await imap.expunge()
    else:
        return False
    return True


async def append_message(
    imap: aioimaplib.IMAP4,
    folder: str,
    raw_message: str,
    flags: str = "",
) -> int | None:
    """Append a message to a folder (for drafts). Returns UID if available."""
    flag_str = f"({flags})" if flags else None
    resp = await imap.append(raw_message.encode("utf-8"), mailbox=_quote_folder(folder), flags=flag_str)
    if resp.result != "OK":
        return None
    for line in _decode_lines(resp.lines):
        m = re.search(r"APPENDUID\s+\d+\s+(\d+)", line)
        if m:
            return int(m.group(1))
    return None
