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
from app.mail.clients.imap_pool import get_pooled_imap
from app.mail.schemas.messages import MoveRequest, FlagRequest, BulkActionRequest

from typing import Optional
import re as _re

def _validate_folder(folder: str) -> str:
    """Validate IMAP folder name: allow letters, digits, spaces, dots, hyphens, underscores, slashes."""
    if not _re.match(r'^[\w\s.\-/&+,()]+$', folder, _re.UNICODE) or len(folder) > 200:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Nombre de carpeta inválido")
    return folder


def _build_unified_search(
    search: str,
    q_from: str | None,
    q_to: str | None,
    q_subject: str | None,
    has_attachment: bool | None,
    date_from: str | None,
    date_to: str | None,
    is_unread: bool | None,
    is_flagged: bool | None,
) -> str:
    """Merge explicit query params into the search string."""
    parts = [search] if search else []
    if q_from:
        parts.append(f"from:{q_from}")
    if q_to:
        parts.append(f"to:{q_to}")
    if q_subject:
        parts.append(f"subject:{q_subject}")
    if has_attachment:
        parts.append("has:attachment")
    if date_from:
        parts.append(f"after:{date_from}")
    if date_to:
        parts.append(f"before:{date_to}")
    if is_unread:
        parts.append("is:unread")
    if is_flagged:
        parts.append("is:flagged")
    return " ".join(parts)


router = APIRouter(prefix="/api/mail", tags=["mail-messages"])


async def _get_imap(request: Request, username: str):
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    return await get_imap_connection(login_user, password)


def _get_pooled(request: Request, username: str):
    """Get pooled IMAP context manager (for read-only operations)."""
    import asyncio
    async def _inner():
        password = await get_user_password(request, username)
        login_user = await get_imap_login_user(request, username)
        return get_pooled_imap(login_user, password)
    return _inner


@router.get("/messages/{folder}")
async def get_messages(
    folder: str,
    request: Request,
    page: int = 1,
    per_page: int = 25,
    search: str = "",
    q_from: str | None = None,
    q_to: str | None = None,
    q_subject: str | None = None,
    has_attachment: bool | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    is_unread: bool | None = None,
    is_flagged: bool | None = None,
    username: str = Depends(get_current_user),
):
    _validate_folder(folder)
    if per_page > 300:
        per_page = 300
    search_query = _build_unified_search(
        search, q_from, q_to, q_subject, has_attachment,
        date_from, date_to, is_unread, is_flagged,
    )
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    async with get_pooled_imap(login_user, password) as imap:
        result = await list_messages(imap, folder, page, per_page, search_query)
        if result is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Folder '{folder}' not found")
        return result


@router.get("/message/{folder}/{uid}")
async def read_message(
    folder: str,
    uid: int,
    request: Request,
    load_images: bool = False,
    username: str = Depends(get_current_user),
):
    _validate_folder(folder)
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    redis = request.app.state.redis
    async with get_pooled_imap(login_user, password) as imap:
        msg = await get_message(imap, folder, uid, block_remote_images=not load_images)
        if msg is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Message not found")
        # FQA-003/004: Invalidate folder/stats cache — fetch_full_message sets \Seen flag
        await redis.delete(f"folders:{username}")
        await redis.delete(f"stats:{username}")
        # Safe Links: reescribir enlaces para protección al hacer clic
        try:
            from app.safelinks import service as sl_service, rewriter as sl_rewriter
            _sl = await sl_service.get_config(request.app.state.db_pool)
            if _sl["enabled"] and _sl["rewrite_enabled"] and msg.get("html_body"):
                msg["html_body"] = sl_rewriter.rewrite(msg["html_body"])
        except Exception:
            pass
        return msg


@router.get("/message/{folder}/{uid}/source")
async def message_source(
    folder: str,
    uid: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    """View raw message source (headers + body)."""
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    async with get_pooled_imap(login_user, password) as imap:
        raw = await fetch_raw_message(imap, folder, uid)
        if raw is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Message not found")
        return {"source": raw}


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
        # FQA-002/003: Invalidate caches after move
        try:
            redis = request.app.state.redis
            await redis.delete(f"folders:{username}")
            await redis.delete(f"stats:{username}")
            # Invalidate UID cache for both source and dest folders
            # Invalidar cache UIDs para source y dest (SCAN en vez de KEYS — O(1) amortizado)
            for pattern in [f"uids:{username}:{folder}:*", f"uids:{username}:{body.dest_folder}:*"]:
                async for k in redis.scan_iter(match=pattern, count=100):
                    await redis.delete(k)
        except Exception:
            pass
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
        # FQA-003/004: Invalidate folder/stats cache when flags change (Seen, Flagged, etc.)
        try:
            redis = request.app.state.redis
            await redis.delete(f"folders:{username}")
            await redis.delete(f"stats:{username}")
        except Exception:
            pass
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
        # FQA-002/003: Invalidate caches after delete
        try:
            redis = request.app.state.redis
            await redis.delete(f"folders:{username}")
            await redis.delete(f"stats:{username}")
            # Invalidar cache UIDs (SCAN en vez de KEYS — O(1) amortizado)
            async for k in redis.scan_iter(match=f"uids:{username}:{folder}:*", count=100):
                await redis.delete(k)
        except Exception:
            pass
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
        # FQA-003/004: Invalidate folder/stats/uid cache after bulk actions
        try:
            redis = request.app.state.redis
            await redis.delete(f"folders:{username}")
            await redis.delete(f"stats:{username}")
            # Invalidar el cache de UIDs de la carpeta: sin esto, tras vaciar/borrar
            # la lista sigue mostrando los mensajes ya eliminados (parecia que no se vaciaba).
            async for k in redis.scan_iter(match=f"uids:{username}:{folder}:*", count=100):
                await redis.delete(k)
            if body.dest_folder:
                async for k in redis.scan_iter(match=f"uids:{username}:{body.dest_folder}:*", count=100):
                    await redis.delete(k)
        except Exception:
            pass
        return {"status": "ok", "count": len(body.uids)}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
