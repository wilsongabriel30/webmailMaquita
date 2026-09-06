"""
Exportar datos — Maquita Webmail
=================================
Exportar correos (.mbox), contactos (.vcf), configuración.
"""

import io
import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import fetch_raw_message, get_imap_connection

logger = logging.getLogger(__name__)
MAX_EXPORT_LIMIT = 200  # Max messages per export to prevent abuse
MAX_EXPORT_SIZE = 10 * 1024 * 1024  # 10 MB max export size


def _validate_export_folder(folder: str) -> str:
    """Validate folder name for export endpoints."""
    if not re.match(r"^[\w\s.\-/&+,()]+$", folder, re.UNICODE) or len(folder) > 200:
        raise HTTPException(status_code=400, detail="Nombre de carpeta inválido")
    return folder




async def _check_export_rate(request, username: str):
    """Rate limit exports: 3 per 5 minutes per user."""
    redis = request.app.state.redis
    key = f"export_rl:{username}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 300)
    if count > 3:
        raise HTTPException(status_code=429, detail="Límite de exportación: máximo 3 por cada 5 minutos")

router = APIRouter(prefix="/api/mail/export", tags=["export"])


@router.get("/mbox/{folder}")
async def export_mbox(
    folder: str,
    request: Request,
    limit: int = 200,
    user: str = Depends(get_current_user),
):
    """Export a folder as .mbox file (RFC 4155)."""
    await _check_export_rate(request, user)
    folder = _validate_export_folder(folder)
    limit = min(limit, MAX_EXPORT_LIMIT)
    from app.mail.clients.imap_client import list_message_uids

    password = await get_user_password(request, user)

    login_user = await get_imap_login_user(request, user)
    imap = await get_imap_connection(login_user, password)
    try:
        uid_result = await list_message_uids(imap, folder, page=1, per_page=limit)
        uids = uid_result.get("uids", [])

        if not uids:
            raise HTTPException(status_code=404, detail="No hay mensajes para exportar")

        # Build mbox content
        mbox_parts = []
        total_size = 0
        for uid in uids:
            try:
                raw = await fetch_raw_message(imap, folder, uid)
                if raw:
                    # mbox format: each message starts with "From " line
                    from_line = f"From {user} {datetime.utcnow().strftime('%a %b %d %H:%M:%S %Y')}\n"
                    # Escape "From " at start of lines in body
                    escaped = raw.replace("\nFrom ", "\n>From ")
                    part = from_line + escaped + "\n"
                    total_size += len(part)
                    if total_size > MAX_EXPORT_SIZE:
                        logger.warning(f"Export size limit reached for {user} in {folder}")
                        break
                    mbox_parts.append(part)
            except Exception as e:
                logger.warning(f"Skip UID {uid}: {e}")
                continue
    finally:
        try:
            await imap.logout()
        except Exception:
            pass

    content = "\n".join(mbox_parts)
    safe_folder = folder.replace("/", "_").replace(" ", "_")
    filename = f"maquita-{safe_folder}-{datetime.utcnow().strftime('%Y%m%d')}.mbox"

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8", errors="replace")),
        media_type="application/mbox",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/contacts")
async def export_contacts_vcf(
    request: Request,
    user: str = Depends(get_current_user),
):
    """Export all contacts as .vcf (vCard 3.0)."""
    await _check_export_rate(request, user)
    db = request.app.state.db_pool

    contacts = await db.fetch(
        "SELECT name, email, phone, organization, notes FROM user_contacts WHERE owner = $1 ORDER BY name",
        user
    )

    vcards = []
    for c in contacts:
        name = c["name"] or c["email"]
        vcard = f"""BEGIN:VCARD
VERSION:3.0
FN:{name}
EMAIL;TYPE=INTERNET:{c['email']}"""
        if c.get("phone"):
            vcard += f"\nTEL;TYPE=WORK:{c['phone']}"
        if c.get("organization"):
            vcard += f"\nORG:{c['organization']}"
        if c.get("notes"):
            vcard += f"\nNOTE:{c['notes']}"
        vcard += "\nEND:VCARD"
        vcards.append(vcard)

    content = "\n".join(vcards)
    filename = f"maquita-contactos-{datetime.utcnow().strftime('%Y%m%d')}.vcf"

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/vcard",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/eml-batch/{folder}")
async def export_eml_batch(
    folder: str,
    request: Request,
    uids: str = "",  # comma-separated UIDs
    user: str = Depends(get_current_user),
):
    """Export multiple emails as individual .eml in a zip archive."""
    await _check_export_rate(request, user)
    folder = _validate_export_folder(folder)
    import zipfile

    if not uids:
        raise HTTPException(status_code=400, detail="Proporciona UIDs separados por coma")

    uid_list = [int(u.strip()) for u in uids.split(",") if u.strip().isdigit()]
    if len(uid_list) > 50:
        raise HTTPException(status_code=400, detail="Máximo 50 mensajes por exportación EML")

    password = await get_user_password(request, user)

    login_user = await get_imap_login_user(request, user)
    imap = await get_imap_connection(login_user, password)
    try:
        buf = io.BytesIO()
        zip_size = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for uid in uid_list:
                try:
                    raw = await fetch_raw_message(imap, folder, uid)
                    if raw:
                        zip_size += len(raw)
                        if zip_size > MAX_EXPORT_SIZE:
                            break
                        zf.writestr(f"message-{uid}.eml", raw)
                except Exception as e:
                    logger.warning(f"Skip UID {uid}: {e}")
        buf.seek(0)
    finally:
        try:
            await imap.logout()
        except Exception:
            pass

    filename = f"maquita-emails-{datetime.utcnow().strftime('%Y%m%d')}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
