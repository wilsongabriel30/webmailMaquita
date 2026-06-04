import os
"""eDiscovery — Búsqueda forense cross-mailbox para el panel de administración."""
import json
import re as _re
import email
import email.header
import hashlib
from datetime import datetime, timezone

import aioimaplib
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/ediscovery", tags=["ediscovery"])

# Configuración IMAP master user (Dovecot)
IMAP_HOST = "127.0.0.1"
IMAP_PORT = 143
MASTER_PASSWORD = os.getenv("MASTER_PASSWORD", "")


def _db(r: Request):
    return r.app.state.db


async def _audit(r, a, action, target=None, details=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )


def _decode_header(val):
    """Decode MIME-encoded header value."""
    if not val:
        return ""
    parts = email.header.decode_header(val)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


@router.get("/mailboxes")
async def list_mailboxes(request: Request, admin: dict = Depends(get_current_admin)):
    """Lista todos los buzones disponibles para búsqueda."""
    db = _db(request)
    rows = await db.fetch("SELECT username, name, active FROM mailbox ORDER BY username")
    return [{"email": r["username"], "name": r["name"], "active": r["active"]} for r in rows]


@router.get("/search")
async def search(
    request: Request,
    q: str = Query(..., min_length=1, description="Término de búsqueda"),
    mailboxes: str = Query(None, description="Buzones (separados por coma). Vacío = todos"),
    folder: str = Query("INBOX", description="Carpeta IMAP"),
    date_from: str = Query(None, description="Desde (DD-Mon-YYYY, ej: 01-Jan-2026)"),
    date_to: str = Query(None, description="Hasta (DD-Mon-YYYY)"),
    field: str = Query("TEXT", description="Campo: TEXT, SUBJECT, FROM, TO, BODY"),
    limit: int = Query(50, le=500, description="Máximo resultados por buzón"),
    admin: dict = Depends(get_current_admin),
):
    """Búsqueda forense cross-mailbox usando IMAP master user."""
    db = _db(request)

    if mailboxes:
        targets = [m.strip() for m in mailboxes.split(",") if m.strip()]
    else:
        rows = await db.fetch("SELECT username FROM mailbox WHERE active = true ORDER BY username")
        targets = [r["username"] for r in rows]

    # Construir criterio IMAP SEARCH
    search_parts = []
    if date_from:
        search_parts.append(f"SINCE {date_from}")
    if date_to:
        search_parts.append(f"BEFORE {date_to}")

    field_upper = (field or "TEXT").upper()
    if field_upper not in ("TEXT", "BODY", "SUBJECT", "FROM", "TO", "CC"):
        field_upper = "TEXT"
    search_parts.append(f'{field_upper} "{q}"')
    search_criteria = " ".join(search_parts)

    await _audit(request, admin, "ediscovery_search", details={
        "query": q, "mailboxes_count": len(targets),
        "folder": folder, "field": field_upper,
    })

    results = []
    errors = []

    for mbox in targets:
        try:
            imap = aioimaplib.IMAP4(host=IMAP_HOST, port=IMAP_PORT, timeout=15)
            await imap.wait_hello_from_server()
            resp = await imap.login(f"{mbox}*admin", MASTER_PASSWORD)
            if resp.result != "OK":
                errors.append({"mailbox": mbox, "error": "Login failed"})
                continue

            resp = await imap.select(folder)
            if resp.result != "OK":
                await imap.logout()
                continue

            resp = await imap.search(search_criteria)
            if resp.result != "OK" or not resp.lines or not resp.lines[0]:
                await imap.logout()
                continue

            msg_ids_raw = resp.lines[0]
            if isinstance(msg_ids_raw, bytes):
                msg_ids_raw = msg_ids_raw.decode()
            msg_ids = msg_ids_raw.strip().split()
            if not msg_ids or msg_ids == [""]:
                await imap.logout()
                continue

            msg_ids = msg_ids[-limit:]

            for mid in msg_ids:
                try:
                    fetch_resp = await imap.fetch(
                        mid,
                        "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO DATE MESSAGE-ID)] RFC822.SIZE)",
                    )
                    if fetch_resp.result == "OK" and fetch_resp.lines:
                        header_data = b""
                        size = 0
                        for line in fetch_resp.lines:
                            raw = (
                                bytes(line)
                                if isinstance(line, (bytes, bytearray))
                                else line.encode() if isinstance(line, str) else None
                            )
                            if raw is None:
                                continue
                            if b"RFC822.SIZE" in raw:
                                size_m = _re.search(rb"RFC822\.SIZE\s+(\d+)", raw)
                                if size_m:
                                    size = int(size_m.group(1))
                            elif raw == b")" or b"completed" in raw.lower():
                                continue
                            else:
                                header_data += raw + b"\r\n"

                        if header_data:
                            msg = email.message_from_bytes(header_data)
                            results.append({
                                "mailbox": mbox,
                                "folder": folder,
                                "uid": mid,
                                "subject": _decode_header(msg.get("Subject", "")),
                                "from": _decode_header(msg.get("From", "")),
                                "to": _decode_header(msg.get("To", "")),
                                "date": msg.get("Date", ""),
                                "message_id": msg.get("Message-ID", ""),
                                "size": size,
                            })
                except Exception:
                    continue

            await imap.logout()
        except Exception as e:
            errors.append({"mailbox": mbox, "error": str(e)[:100]})

    results.sort(key=lambda r: r.get("date", ""), reverse=True)

    return {
        "query": q,
        "field": field_upper,
        "folder": folder,
        "total_results": len(results),
        "mailboxes_searched": len(targets),
        "mailboxes_with_errors": len(errors),
        "results": results,
        "errors": errors if errors else None,
    }


@router.get("/export/{mailbox}")
async def export_message(
    mailbox: str,
    uid: str = Query(...),
    folder: str = Query("INBOX"),
    request: Request = None,
    admin: dict = Depends(get_current_admin),
):
    """Exportar mensaje como .eml con metadata forense (cadena de custodia)."""
    await _audit(request, admin, "ediscovery_export", target=mailbox, details={
        "uid": uid, "folder": folder,
    })

    try:
        imap = aioimaplib.IMAP4(host=IMAP_HOST, port=IMAP_PORT, timeout=15)
        await imap.wait_hello_from_server()
        resp = await imap.login(f"{mailbox}*admin", MASTER_PASSWORD)
        if resp.result != "OK":
            raise HTTPException(502, "No se pudo acceder al buzón")

        resp = await imap.select(folder)
        if resp.result != "OK":
            raise HTTPException(404, "Carpeta no encontrada")

        resp = await imap.fetch(uid, "(RFC822)")
        if resp.result != "OK":
            raise HTTPException(404, "Mensaje no encontrado")

        raw_email = b""
        for line in resp.lines:
            raw = bytes(line) if isinstance(line, (bytes, bytearray)) else None
            if raw is None:
                continue
            if raw == b")" or b"FETCH" in raw or b"completed" in raw.lower():
                continue
            raw_email += raw + b"\r\n"

        await imap.logout()

        sha256 = hashlib.sha256(raw_email).hexdigest()
        export_time = datetime.now(timezone.utc).isoformat()
        safe_uid = uid.replace("/", "_")

        headers = {
            "Content-Disposition": f'attachment; filename="{mailbox}_{safe_uid}.eml"',
            "Content-Type": "message/rfc822",
            "X-eDiscovery-Source": mailbox,
            "X-eDiscovery-Folder": folder,
            "X-eDiscovery-UID": uid,
            "X-eDiscovery-SHA256": sha256,
            "X-eDiscovery-ExportedAt": export_time,
            "X-eDiscovery-ExportedBy": admin["username"],
        }

        return StreamingResponse(
            iter([raw_email]),
            media_type="message/rfc822",
            headers=headers,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error exportando: {str(e)[:200]}")
