"""Attachments router — download and preview attachments by UID and part number."""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import Response
import mimetypes

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password
from app.mail.clients.imap_client import get_imap_connection, fetch_attachment

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
    password = await get_user_password(request, username)
    imap = await get_imap_connection(username, password)
    try:
        data = await fetch_attachment(imap, folder, uid, part_number)
        if data is None:
            raise HTTPException(status_code=404, detail="Attachment not found")

        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = "application/octet-stream"

        return Response(
            content=data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
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
    password = await get_user_password(request, username)

    content_type, _ = mimetypes.guess_type(filename)
    if not content_type:
        content_type = "application/octet-stream"

    # Check if previewable
    is_image = content_type in _PREVIEWABLE_IMAGE or content_type.startswith("image/")
    is_pdf = content_type == "application/pdf"
    is_text = content_type in _PREVIEWABLE_TEXT

    if not (is_image or is_pdf or is_text):
        raise HTTPException(status_code=415, detail="Preview not supported for this file type")

    imap = await get_imap_connection(username, password)
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
            },
        )
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
