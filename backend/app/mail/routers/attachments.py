"""Attachments router — download and preview attachments by UID and part number."""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import Response
import mimetypes

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password, get_imap_login_user
from app.mail.clients.imap_client import get_imap_connection, fetch_attachment

import re as _re

def _validate_folder(folder: str) -> str:
    if not _re.match(r'^[\w\s.\-/&+,()]+$', folder, _re.UNICODE) or len(folder) > 200:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Nombre de carpeta inválido")
    return folder

router = APIRouter(prefix="/api/mail", tags=["mail-attachments"])

# MIME types that support inline preview
_PREVIEWABLE_IMAGE = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml", "image/bmp"}
_PREVIEWABLE_TEXT = {"text/plain", "text/csv", "text/html", "text/xml", "text/css", "text/javascript", "application/json"}


@router.get("/attachment/{folder}/{uid}/{part_number}/{filename}")
async def download_attachment(
    folder: str,
    uid: int,
    part_number: str,
    filename: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    _validate_folder(folder)
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        data = await fetch_attachment(imap, folder, uid, part_number)
        if data is None:
            raise HTTPException(status_code=404, detail="Attachment not found")

        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = "application/octet-stream"
        # Fallback: si la extensión es conocida, corregir octet-stream
        if content_type == "application/octet-stream":
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            ext_map = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                       "png": "image/png", "gif": "image/gif", "svg": "image/svg+xml"}
            content_type = ext_map.get(ext, content_type)

        return Response(
            content=data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.get("/preview/{folder}/{uid}/{part_number}/{filename}")
async def preview_attachment(
    folder: str,
    uid: int,
    part_number: str,
    filename: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Return attachment inline for preview (images, PDFs, text files)."""
    _validate_folder(folder)
    password = await get_user_password(request, username)

    content_type, _ = mimetypes.guess_type(filename)
    if not content_type:
        content_type = "application/octet-stream"

    # Muchos servidores envían PDFs como application/octet-stream.
    # Usar la extensión del archivo como fallback para detectar el tipo real.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if content_type == "application/octet-stream" and ext == "pdf":
        content_type = "application/pdf"

    # Check if previewable
    is_image = content_type in _PREVIEWABLE_IMAGE or content_type.startswith("image/")
    is_pdf = content_type == "application/pdf"
    is_text = content_type in _PREVIEWABLE_TEXT

    if not (is_image or is_pdf or is_text):
        raise HTTPException(status_code=415, detail="Preview not supported for this file type")

    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        data = await fetch_attachment(imap, folder, uid, part_number)
        if data is None:
            raise HTTPException(status_code=404, detail="Attachment not found")

        return Response(
            content=data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Cache-Control": "private, max-age=300",
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.get("/attachments-zip/{folder}/{uid}")
async def download_all_attachments_zip(
    folder: str,
    uid: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Download all non-inline attachments of a message as a single ZIP file."""
    import io
    import zipfile
    from app.mail.services.message_service import get_message

    _validate_folder(folder)
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        # Get message to find all attachments
        msg = await get_message(imap, folder, uid, block_remote_images=False)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")

        attachments = msg.get("attachments", [])
        # Filter non-inline attachments
        real_attachments = [a for a in attachments if not a.get("is_inline", False)]
        if not real_attachments:
            raise HTTPException(status_code=404, detail="No attachments found")

        # Need a new IMAP connection for fetching each attachment
        # (the first one was used for read_message)
        imap2 = await get_imap_connection(login_user, password)
        try:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                seen_names = {}
                for att in real_attachments:
                    data = await fetch_attachment(imap2, folder, uid, att["part_number"])
                    if data:
                        fname = att.get("filename", "adjunto")
                        # Handle duplicate filenames
                        if fname in seen_names:
                            seen_names[fname] += 1
                            name, ext = fname.rsplit('.', 1) if '.' in fname else (fname, '')
                            fname = f"{name} ({seen_names[fname]}).{ext}" if ext else f"{name} ({seen_names[fname]})"
                        else:
                            seen_names[fname] = 0
                        zf.writestr(fname, data)
            buf.seek(0)
            zip_data = buf.getvalue()
        finally:
            try:
                await imap2.logout()
            except Exception:
                pass

        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="adjuntos_{uid}.zip"',
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
