"""Messages router — list, read, move, flag, bulk, download .eml, view source."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password, get_imap_login_user
from app.mail.clients.imap_client import (
    get_imap_connection, uid_move_message, uid_set_flags,
    uid_delete_message, uid_bulk_action, fetch_raw_message,
)
from app.mail.services.message_service import list_messages, get_message
from app.mail.schemas.messages import MoveRequest, FlagRequest, BulkActionRequest

import re as _re

def _validate_folder(folder: str) -> str:
    """Validate IMAP folder name: allow letters, digits, spaces, dots, hyphens, underscores, slashes."""
    if not _re.match(r'^[\w\s.\-/&+,()]+$', folder, _re.UNICODE) or len(folder) > 200:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Nombre de carpeta inválido")
    return folder


router = APIRouter(prefix="/api/mail", tags=["mail-messages"])


async def _get_imap(request: Request, username: str):
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    return await get_imap_connection(login_user, password)


@router.get("/messages/{folder}")
async def get_messages(
    folder: str,
    request: Request,
    page: int = 1,
    per_page: int = 25,
    search: str = "",
    username: str = Depends(get_current_user),
):
    _validate_folder(folder)
    if per_page > 100:
        per_page = 100
    imap = await _get_imap(request, username)
    try:
        result = await list_messages(imap, folder, page, per_page, search)
        if result is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Folder '{folder}' not found")
        return result
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.get("/message/{folder}/{uid}")
async def read_message(
    folder: str,
    uid: int,
    request: Request,
    load_images: bool = False,
    username: str = Depends(get_current_user),
):
    _validate_folder(folder)
    imap = await _get_imap(request, username)
    try:
        msg = await get_message(imap, folder, uid, block_remote_images=not load_images)
        if msg is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Message not found")
        return msg
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.get("/message/{folder}/{uid}/source")
async def message_source(
    folder: str,
    uid: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    """View raw message source (headers + body)."""
    imap = await _get_imap(request, username)
    try:
        raw = await fetch_raw_message(imap, folder, uid)
        if raw is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Message not found")
        return {"source": raw}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.get("/message/{folder}/{uid}/eml")
async def download_eml(
    folder: str,
    uid: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Download message as .eml file."""
    imap = await _get_imap(request, username)
    try:
        raw = await fetch_raw_message(imap, folder, uid)
        if raw is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Message not found")
        return Response(
            content=raw.encode("utf-8"),
            media_type="message/rfc822",
            headers={"Content-Disposition": f'attachment; filename="message-{uid}.eml"'},
        )
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.post("/move/{folder}/{uid}")
async def move(
    folder: str,
    uid: int,
    body: MoveRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    _validate_folder(folder)
    _validate_folder(body.dest_folder)
    imap = await _get_imap(request, username)
    try:
        ok = await uid_move_message(imap, folder, uid, body.dest_folder)
        if not ok:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Message not found or destination folder invalid")
        return {"status": "moved"}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.post("/flags/{folder}/{uid}")
async def update_flags(
    folder: str,
    uid: int,
    body: FlagRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    imap = await _get_imap(request, username)
    try:
        ok = await uid_set_flags(imap, folder, uid, body.flags, body.add)
        if not ok:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Failed to update flags")
        return {"status": "updated"}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.delete("/message/{folder}/{uid}")
async def remove_message(
    folder: str,
    uid: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    _validate_folder(folder)
    imap = await _get_imap(request, username)
    try:
        ok = await uid_delete_message(imap, folder, uid)
        if not ok:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Message not found or could not be deleted")
        return {"status": "deleted"}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.post("/bulk-action/{folder}")
async def bulk_action(
    folder: str,
    body: BulkActionRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    _validate_folder(folder)
    imap = await _get_imap(request, username)
    try:
        ok = await uid_bulk_action(imap, folder, body.uids, body.action, body.dest_folder)
        if not ok:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Failed to perform bulk action")
        return {"status": "ok", "count": len(body.uids)}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
