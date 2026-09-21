"""Messages router — list, read, move, flag, bulk, download .eml, view source."""

import re as _re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import (
    fetch_raw_message,
    get_imap_connection,
    uid_bulk_action,
    uid_delete_message,
    uid_move_message,
    uid_set_flags,
)
from app.mail.clients.imap_pool import get_pooled_imap
from app.mail.schemas.messages import BulkActionRequest, FlagRequest, MoveRequest
from app.mail.services.cache_uids import invalidar_uids
from app.mail.services.message_service import get_message, list_messages


def _validate_folder(folder: str) -> str:
    """Validate IMAP folder name: allow letters, digits, spaces, dots, hyphens, underscores, slashes."""
    if not _re.match(r"^[\w\s.\-/&+,()@]+$", folder, _re.UNICODE) or len(folder) > 200:
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
    q_domain: str | None = None,
    q_from_domain: str | None = None,
    min_size: str | None = None,
    max_size: str | None = None,
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
    # Acotar por dominio es lo que se pide cuando no se recuerda el remitente exacto
    # («era alguien de Andes»). Va por cabecera: decenas de milisegundos.
    if q_domain:
        parts.append(f"dominio:{q_domain}")
    if q_from_domain:
        parts.append(f"de-dominio:{q_from_domain}")
    if min_size:
        parts.append(f"larger:{min_size}")
    if max_size:
        parts.append(f"smaller:{max_size}")
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
    q_domain: str | None = None,
    q_from_domain: str | None = None,
    min_size: str | None = None,
    max_size: str | None = None,
    buscar_en_contenido: bool = False,
    username: str = Depends(get_current_user),
):
    _validate_folder(folder)
    if per_page > 300:
        per_page = 300
    search_query = _build_unified_search(
        search,
        q_from,
        q_to,
        q_subject,
        has_attachment,
        date_from,
        date_to,
        is_unread,
        is_flagged,
        q_domain,
        q_from_domain,
        min_size,
        max_size,
    )
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    async with get_pooled_imap(login_user, password) as imap:
        # En las cuentas con indice de texto la busqueda entra tambien en el cuerpo: medido en
        # Enviados de gerencia comercial (19.432 mensajes), 0,13 s y 586 resultados frente a 24
        # mirando solo cabeceras. Sin indice hay que abrir y descifrar los mensajes uno a uno
        # -minuto y medio-, asi que ahi solo se hace si quien busca lo pide.
        # `username` hace falta para saber si la cuenta tiene indice de texto: sin el,
        # `cuenta_indexada("")` era siempre False, la busqueda no entraba nunca en el
        # cuerpo y `contenido:` se acotaba en silencio al ultimo ano, escondiendo el
        # historico a quien buscaba en Enviados (21/09/2026).
        # `redis` se deja fuera a proposito: la cache de UIDs (300 s) retrasaba la
        # aparicion del correo recien llegado.
        result = await list_messages(
            imap,
            folder,
            page,
            per_page,
            search_query,
            username=username,
            buscar_en_contenido=buscar_en_contenido,
        )
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
            from app.safelinks import rewriter as sl_rewriter
            from app.safelinks import service as sl_service

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
            headers={
                "Content-Disposition": f'attachment; filename="message-{uid}.eml"'
            },
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
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    async with get_pooled_imap(login_user, password) as imap:
        ok = await uid_move_message(imap, folder, uid, body.dest_folder)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Message not found or destination folder invalid",
        )
    await invalidar_uids(request.app.state.redis, username, folder, body.dest_folder)
    return {"status": "moved"}


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
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    async with get_pooled_imap(login_user, password) as imap:
        ok = await uid_delete_message(imap, folder, uid)
    if not ok:
        raise HTTPException(
            status_code=404, detail="Message not found or could not be deleted"
        )
    await invalidar_uids(request.app.state.redis, username, folder)
    return {"status": "deleted"}


@router.post("/bulk-action/{folder}")
async def bulk_action(
    folder: str,
    body: BulkActionRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    _validate_folder(folder)
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    async with get_pooled_imap(login_user, password) as imap:
        ok = await uid_bulk_action(
            imap, folder, body.uids, body.action, body.dest_folder
        )
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to perform bulk action")
    # Sin esto, tras vaciar/borrar la lista seguía mostrando los mensajes eliminados.
    await invalidar_uids(request.app.state.redis, username, folder, body.dest_folder)
    return {"status": "ok", "count": len(body.uids)}
