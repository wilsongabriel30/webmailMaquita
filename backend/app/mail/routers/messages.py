"""Messages router — list, read, move, flag, bulk, download .eml, view source."""

import asyncio
import re as _re
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail import telemetria_busqueda
from app.mail.clients.imap_client import (
    fetch_raw_message,
    get_imap_connection,
    uid_bulk_action_detallado,
    uid_delete_message,
    uid_move_message_detallado,
    uid_set_flags,
)
from app.mail.clients.imap_pool import es_conexion_caida, get_pooled_imap
from app.mail.nombre_carpeta import nombre_valido
from app.mail.schemas.messages import BulkActionRequest, FlagRequest, MoveRequest
from app.mail.services import etiquetas_reubicar, reacciones
from app.mail.services.cache_uids import invalidar_uids
from app.mail.services.message_service import get_message, list_messages
from app.rag import eliminar as rag_eliminar


def _validate_folder(folder: str) -> str:
    """Validate IMAP folder name: allow letters, digits, spaces, dots, hyphens, underscores, slashes."""
    if not nombre_valido(folder):
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
    conexion = get_pooled_imap(login_user, password)
    async with conexion as imap:
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
        t0 = time.monotonic()
        # 06/11/2026: «Gissela» encuentra también los correos de su dirección aunque traigan un cargo.
        from app.mail.busqueda_por_nombre import direcciones_de_nombre

        direcciones = (
            await direcciones_de_nombre(
                request.app.state.db_pool, username, search_query
            )
            if search_query.strip()
            else []
        )

        async def _listar(con):
            return await list_messages(
                con,
                folder,
                page,
                per_page,
                search_query,
                username=username,
                buscar_en_contenido=buscar_en_contenido,
                direcciones_nombre=direcciones,
                # Solo para la caché de adjuntos (07/11/2026); la lista de UIDs sigue sin caché aquí.
                redis_adjuntos=getattr(request.app.state, "redis", None),
            )

        try:
            result = await _listar(imap)
        except Exception as exc:
            # La conexión del fondo se cerró en mitad del uso: una sola vuelta con una nueva.
            if not es_conexion_caida(exc):
                raise
            imap = await conexion.reconectar()
            result = await _listar(imap)
        if result is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"Folder '{folder}' not found")
        if search_query.strip():
            # Telemetría de búsqueda (05/11/2026): queda qué se buscó, dónde y con qué resultado.
            total = result.get("total") if isinstance(result, dict) else None
            asyncio.create_task(
                telemetria_busqueda.registrar(
                    request.app.state.db_pool,
                    username,
                    folder,
                    search_query,
                    total,
                    int((time.monotonic() - t0) * 1000),
                    buscar_en_contenido,
                    page,
                )
            )
        # Marca de reacciones en la lista (una consulta por página; sin ella el listado sale igual).
        if isinstance(result, dict):
            await reacciones.anotar_en_lista(
                request.app.state.db_pool, result.get("messages") or []
            )
        return result


@router.get("/message/{folder}/{uid}")
async def read_message(
    folder: str,
    uid: int,
    request: Request,
    load_images: bool = False,
    marcar_leido: bool = True,
    username: str = Depends(get_current_user),
):
    # marcar_leido=false: lo usa la descarga para leer sin conexion y la carga de adjuntos,
    # que piden el correo sin que nadie lo haya abierto. Sin esto, los correos nuevos
    # quedaban como leidos solos.
    _validate_folder(folder)
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    redis = request.app.state.redis
    from app.mail.services.imagenes_remotas import debe_bloquear

    bloquear = not load_images and await debe_bloquear(
        request.app.state.db_pool, username, folder
    )
    async with get_pooled_imap(login_user, password) as imap:
        msg = await get_message(
            imap, folder, uid, block_remote_images=bloquear, mark_seen=marcar_leido
        )
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
                from app.portales import direcciones

                msg["html_body"] = sl_rewriter.rewrite(
                    msg["html_body"],
                    await direcciones.url_de_peticion(
                        request.app.state.db_pool, request
                    ),
                )
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
    db = request.app.state.db_pool
    async with get_pooled_imap(login_user, password) as imap:
        ctx = await etiquetas_reubicar.preparar_reubicacion(
            db, imap, username, folder, [uid], "move"
        )
        ok, mapa = await uid_move_message_detallado(imap, folder, uid, body.dest_folder)
        if ok:
            # Las etiquetas siguen al correo (09/11/2026).
            await etiquetas_reubicar.completar_reubicacion(
                db, imap, ctx, mapa, body.dest_folder
            )
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Message not found or destination folder invalid",
        )
    await invalidar_uids(request.app.state.redis, username, folder, body.dest_folder)
    movidos = {str(k): v for k, v in (mapa or {}).items()}
    return {"status": "moved", "movidos": movidos}


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
    # Eliminado definitivo: sus asignaciones de etiqueta sobran (09/11/2026).
    await etiquetas_reubicar.completar_reubicacion(
        request.app.state.db_pool,
        None,
        {"owner": username, "folder": folder, "uids": [uid], "action": "delete"},
        None,
        "",
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
    db = request.app.state.db_pool
    async with get_pooled_imap(login_user, password) as imap:
        ctx = await etiquetas_reubicar.preparar_reubicacion(
            db, imap, username, folder, body.uids, body.action
        )
        ok, mapa = await uid_bulk_action_detallado(
            imap, folder, body.uids, body.action, body.dest_folder
        )
        if ok:
            # Las etiquetas siguen al correo movido/archivado y se borran al eliminar (09/11/2026).
            await etiquetas_reubicar.completar_reubicacion(
                db, imap, ctx, mapa, body.dest_folder
            )
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to perform bulk action")
    # Sin esto, tras vaciar/borrar la lista seguía mostrando los mensajes eliminados.
    await invalidar_uids(request.app.state.redis, username, folder, body.dest_folder)
    # El asistente deja de «ver» al instante lo eliminado o movido (08/11/2026).
    await rag_eliminar.tras_accion(
        request.app.state.db_pool, username, folder, body.uids, body.action
    )
    # «Deshacer» del webmail: con el mapa COPYUID devuelve los correos a su carpeta (10/11/2026).
    movidos = {str(k): v for k, v in (mapa or {}).items()} if ok else {}
    return {"status": "ok", "count": len(body.uids), "movidos": movidos}
