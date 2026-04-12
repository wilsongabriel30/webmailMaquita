"""Attachment search router — search inside attachment content using Apache Tika."""
import logging
import httpx
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from app.auth.dependencies import get_current_user
from app.core.session import get_user_password, get_imap_login_user
from app.mail.clients.imap_client import get_imap_connection

logger = logging.getLogger("search_attachments")

TIKA_URL = "http://127.0.0.1:9998/tika"

router = APIRouter(prefix="/api/mail/search", tags=["mail-search"])


async def _get_imap(request: Request, username: str):
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    return await get_imap_connection(login_user, password)


async def _extract_text_tika(content: bytes, content_type: str = "application/octet-stream") -> str:
    """Send binary content to Tika and get extracted text."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.put(
                TIKA_URL,
                content=content,
                headers={"Content-Type": content_type},
            )
            if resp.status_code == 200:
                return resp.text
    except Exception as e:
        logger.warning(f"Tika extraction failed: {e}")
    return ""


@router.get("/attachments")
async def search_attachments(
    request: Request,
    q: str = Query(..., min_length=1, description="Texto a buscar en adjuntos"),
    folder: str = Query("INBOX", description="Carpeta IMAP"),
    limit: int = Query(50, ge=1, le=200),
    username: str = Depends(get_current_user),
):
    """Buscar texto dentro del contenido de adjuntos usando Apache Tika."""
    imap = await _get_imap(request, username)
    try:
        # Select folder
        await imap.select(folder)

        # Search messages with attachments
        search_criteria = "HEADER Content-Type multipart/mixed"
        _, data = await imap.search(search_criteria)
        if not data or not data[0]:
            return {"results": [], "total": 0, "query": q}

        uids = data[0].split()
        # Limit scan to most recent messages
        uids = uids[-min(len(uids), 500):]

        results = []
        query_lower = q.lower()

        for uid in reversed(uids):
            if len(results) >= limit:
                break

            try:
                # Fetch message structure
                _, msg_data = await imap.fetch(uid.decode(), "(BODYSTRUCTURE ENVELOPE)")
                if not msg_data or not msg_data[0]:
                    continue

                # Parse envelope for subject/from
                envelope_data = msg_data[0]

                # Fetch full message to extract attachments
                _, full_data = await imap.fetch(uid.decode(), "(BODY.PEEK[])")
                if not full_data or not full_data[0]:
                    continue

                raw_msg = full_data[0][1] if isinstance(full_data[0], tuple) else None
                if not raw_msg:
                    continue

                import email
                msg = email.message_from_bytes(raw_msg)

                subject = msg.get("Subject", "")
                from_addr = msg.get("From", "")
                date_str = msg.get("Date", "")

                # Walk through parts looking for attachments
                for part in msg.walk():
                    content_disposition = str(part.get("Content-Disposition", ""))
                    if "attachment" not in content_disposition:
                        continue

                    filename = part.get_filename() or "unknown"
                    content_type = part.get_content_type()
                    payload = part.get_payload(decode=True)

                    if not payload:
                        continue

                    # Extract text via Tika
                    extracted = await _extract_text_tika(payload, content_type)

                    if extracted and query_lower in extracted.lower():
                        # Found match
                        # Find snippet around match
                        idx = extracted.lower().find(query_lower)
                        start = max(0, idx - 80)
                        end = min(len(extracted), idx + len(q) + 80)
                        snippet = extracted[start:end].strip()

                        results.append({
                            "uid": uid.decode(),
                            "folder": folder,
                            "subject": subject,
                            "from": from_addr,
                            "date": date_str,
                            "attachment_name": filename,
                            "content_type": content_type,
                            "snippet": f"...{snippet}...",
                        })
                        break  # One match per message is enough

            except Exception as e:
                logger.debug(f"Error processing uid {uid}: {e}")
                continue

        return {"results": results, "total": len(results), "query": q}

    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.get("/advanced")
async def search_advanced(
    request: Request,
    q: str = Query(..., min_length=1, description="Texto a buscar"),
    in_fields: str = Query("body,subject", alias="in", description="Campos: body,subject,attachments"),
    folder: str = Query("INBOX", description="Carpeta IMAP"),
    username: str = Depends(get_current_user),
):
    """Busqueda avanzada: body, subject, y/o attachments."""
    fields = [f.strip() for f in in_fields.split(",")]
    results = {"query": q, "folder": folder, "fields": fields}

    imap = await _get_imap(request, username)
    try:
        await imap.select(folder)

        # IMAP search for body/subject
        imap_results = []
        if "body" in fields or "subject" in fields:
            criteria_parts = []
            if "body" in fields and "subject" in fields:
                criteria_parts = [f'OR BODY "{q}" SUBJECT "{q}"']
            elif "body" in fields:
                criteria_parts = [f'BODY "{q}"']
            elif "subject" in fields:
                criteria_parts = [f'SUBJECT "{q}"']

            for criteria in criteria_parts:
                _, data = await imap.search(criteria)
                if data and data[0]:
                    imap_results.extend(data[0].split())

        # Remove duplicates
        seen_uids = set()
        unique_uids = []
        for uid in imap_results:
            if uid not in seen_uids:
                seen_uids.add(uid)
                unique_uids.append(uid)

        # Build result list from IMAP matches
        msg_results = []
        for uid in unique_uids[-50:]:
            try:
                _, msg_data = await imap.fetch(uid.decode(), "(ENVELOPE)")
                if msg_data and msg_data[0]:
                    import email.header
                    raw = msg_data[0]
                    msg_results.append({
                        "uid": uid.decode(),
                        "folder": folder,
                        "source": "imap",
                    })
            except Exception:
                continue

        results["imap_matches"] = len(msg_results)
        results["messages"] = msg_results

        # Attachment search if requested
        if "attachments" in fields:
            results["attachment_search"] = "Use /api/mail/search/attachments?q= for full attachment content search"

        return results

    finally:
        try:
            await imap.logout()
        except Exception:
            pass
