"""Import masivo: contacts (CSV/vCard) and emails (MBOX/EML)."""

import asyncio
import csv
import email
import io
import logging
import mailbox
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.config import get_settings as _cfg

logger = logging.getLogger("import_export")

router = APIRouter(prefix="/api/import", tags=["import"])

# ---------- Helpers ----------

# _get_user_id removed in Fase 2 cleanup - using user_email directly


async def _create_job(db, user_email: str, job_type: str) -> str:
    job_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO import_jobs (id, user_email, type, status, started_at)
           VALUES ($1, $2, $3, 'processing', NOW())""",
        job_id,
        user_email,
        job_type,
    )
    return job_id


async def _update_job(db, job_id: str, **kwargs):
    set_parts = []
    values = []
    for i, (k, v) in enumerate(kwargs.items(), 1):
        set_parts.append(f"{k} = ${i}")
        values.append(v)
    values.append(job_id)
    await db.execute(
        f"UPDATE import_jobs SET {', '.join(set_parts)} WHERE id = ${len(values)}",
        *values,
    )


# ---------- Contact import ----------


def _parse_vcard(text: str) -> list[dict]:
    """Simple vCard parser — extracts FN, EMAIL, TEL, ORG."""
    contacts = []
    current = {}
    for line in text.splitlines():
        line = line.strip()
        if line.upper() == "BEGIN:VCARD":
            current = {}
        elif line.upper() == "END:VCARD":
            if current.get("email"):
                contacts.append(current)
            current = {}
        elif ":" in line:
            key, _, value = line.partition(":")
            key = key.split(";")[0].upper()
            if key == "FN":
                current["name"] = value
            elif key == "EMAIL":
                current["email"] = value
            elif key == "TEL":
                current["phone"] = value
            elif key == "ORG":
                current["company"] = value
    return contacts


async def _import_contacts_task(db, user_email: str, job_id: str, contacts: list[dict]):
    """Background task to bulk-insert contacts."""
    total = len(contacts)
    await _update_job(db, job_id, total=total, status="processing")
    processed = 0
    errors = 0
    error_details = []
    for c in contacts:
        try:
            await db.execute(
                """INSERT INTO contacts (user_email, name, email, phone, company)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (user_email, email) DO UPDATE SET
                     name = COALESCE(EXCLUDED.name, contacts.name),
                     phone = COALESCE(EXCLUDED.phone, contacts.phone),
                     company = COALESCE(EXCLUDED.company, contacts.company)""",
                user_email,
                c.get("name", ""),
                c.get("email", ""),
                c.get("phone"),
                c.get("company"),
            )
            processed += 1
        except Exception as e:
            errors += 1
            error_details.append(
                {"contact": c.get("email", "unknown"), "error": str(e)[:200]}
            )
            logger.warning("Import contact error: %s", e)
    import json

    await _update_job(
        db,
        job_id,
        processed=processed,
        errors=errors,
        status="completed",
        error_details=json.dumps(error_details) if error_details else None,
        completed_at=datetime.now(timezone.utc),
    )


# [R-03] Límite en aplicación por endpoint (nginx es la segunda capa) y lectura a disco en
# trozos: nunca el upload completo en memoria.
async def _guardar_upload(file, max_mb: int):
    import tempfile as _tf

    limite = max_mb * 1024 * 1024
    tmp = _tf.NamedTemporaryFile(delete=False)
    total = 0
    try:
        while True:
            trozo = await file.read(1024 * 1024)
            if not trozo:
                break
            total += len(trozo)
            if total > limite:
                raise HTTPException(413, f"El archivo supera el máximo de {max_mb} MB")
            tmp.write(trozo)
        tmp.close()
        return tmp.name, total
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise


@router.post("/contacts")
async def import_contacts(
    request: Request,
    bg: BackgroundTasks,
    file: UploadFile = File(...),
    username: str = Depends(get_current_user),
):
    db = request.app.state.db_pool
    ruta_tmp, _n = await _guardar_upload(file, _cfg().import_contacts_max_mb)
    try:
        with open(ruta_tmp, "rb") as _f:
            content = _f.read().decode("utf-8", errors="replace")
    finally:
        os.unlink(ruta_tmp)
    filename = (file.filename or "").lower()

    if filename.endswith(".vcf") or filename.endswith(".vcard"):
        contacts = _parse_vcard(content)
    elif filename.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(content))
        contacts = [dict(row) for row in reader]
    else:
        raise HTTPException(400, "Unsupported file format. Use .csv or .vcf")

    if not contacts:
        raise HTTPException(400, "No contacts found in file")

    job_id = await _create_job(db, username, "contacts")
    await _update_job(db, job_id, total=len(contacts))
    bg.add_task(_import_contacts_task, db, username, job_id, contacts)
    return {"job_id": job_id, "total": len(contacts), "status": "processing"}


# ---------- Email import ----------


async def _import_emails_task(
    db, user_email: str, job_id: str, username: str, messages: list[bytes]
):
    """Background task to inject emails via LMTP."""
    total = len(messages)
    await _update_job(db, job_id, total=total, status="processing")
    processed = 0
    errors = 0
    error_details = []

    for msg_bytes in messages:
        try:
            # Inject via LMTP to localhost:24
            reader, writer = await asyncio.open_connection("127.0.0.1", 24)
            greeting = await asyncio.wait_for(reader.readline(), timeout=5)

            async def _send(cmd: str):
                writer.write((cmd + "\r\n").encode())
                await writer.drain()
                return (await asyncio.wait_for(reader.readline(), timeout=5)).decode()

            await _send(f"LHLO import.local")
            # Read possible multi-line response
            while True:
                line = (await asyncio.wait_for(reader.readline(), timeout=5)).decode()
                if line[3] == " ":
                    break

            _ie_settings = get_settings()
            await _send(f"MAIL FROM:<import@{_ie_settings.mail_domain}>")
            await _send(f"RCPT TO:<{username}>")
            resp = await _send("DATA")
            if not resp.startswith("354"):
                raise Exception(f"LMTP DATA rejected: {resp}")
            # Send message data
            writer.write(msg_bytes)
            if not msg_bytes.endswith(b"\r\n"):
                writer.write(b"\r\n")
            writer.write(b".\r\n")
            await writer.drain()
            final = (await asyncio.wait_for(reader.readline(), timeout=10)).decode()
            await _send("QUIT")
            writer.close()

            if final.startswith("250"):
                processed += 1
            else:
                errors += 1
                error_details.append({"error": final.strip()[:200]})
        except Exception as e:
            errors += 1
            error_details.append({"error": str(e)[:200]})
            logger.warning("Import email error: %s", e)

    import json

    await _update_job(
        db,
        job_id,
        processed=processed,
        errors=errors,
        status="completed",
        error_details=json.dumps(error_details) if error_details else None,
        completed_at=datetime.now(timezone.utc),
    )


@router.post("/emails")
async def import_emails(
    request: Request,
    bg: BackgroundTasks,
    file: UploadFile = File(...),
    username: str = Depends(get_current_user),
):
    db = request.app.state.db_pool
    filename = (file.filename or "").lower()
    if not (filename.endswith(".eml") or filename.endswith(".mbox")):
        raise HTTPException(400, "Unsupported file format. Use .eml or .mbox")
    tmp_path, _n = await _guardar_upload(file, _cfg().import_emails_max_mb)
    messages = []
    if filename.endswith(".eml"):
        with open(tmp_path, "rb") as _f:
            messages.append(_f.read())
        os.unlink(tmp_path)
    elif filename.endswith(".mbox"):
        # [R-03] mailbox.mbox lee del disco: el archivo nunca entra completo en memoria
        try:
            mbox = mailbox.mbox(tmp_path)
            for msg in mbox:
                messages.append(msg.as_bytes())
            mbox.close()
        finally:
            os.unlink(tmp_path)
    else:
        raise HTTPException(400, "Unsupported file format. Use .eml or .mbox")

    if not messages:
        raise HTTPException(400, "No emails found in file")

    job_id = await _create_job(db, username, "emails")
    await _update_job(db, job_id, total=len(messages))
    bg.add_task(_import_emails_task, db, username, job_id, username, messages)
    return {"job_id": job_id, "total": len(messages), "status": "processing"}


# ---------- Import status ----------


@router.get("/status/{job_id}")
async def import_status(
    job_id: str, request: Request, username: str = Depends(get_current_user)
):
    db = request.app.state.db_pool

    row = await db.fetchrow(
        "SELECT * FROM import_jobs WHERE id = $1 AND user_email = $2",
        job_id,
        username,
    )
    if not row:
        raise HTTPException(404, "Import job not found")
    d = dict(row)
    for k in ("started_at", "completed_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
        else:
            d[k] = None
    if d.get("error_details") and isinstance(d["error_details"], str):
        import json

        d["error_details"] = json.loads(d["error_details"])
    return d
