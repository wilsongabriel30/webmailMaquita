import logging
logger = logging.getLogger(__name__)
"""Folders router — list, create, rename, delete, move folders."""
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password, get_imap_login_user
# IMPORTANTE: Todas las operaciones IMAP requieren nombres de carpeta en Modified UTF-7.
# Los nombres llegan del frontend como UTF-8 (display name) y se convierten con _imap_utf7_encode.
# Sin esta conversión, carpetas con tildes/ñ/caracteres especiales fallan silenciosamente.
from app.mail.clients.imap_client import get_imap_connection, _imap_utf7_encode
from app.mail.services.folder_service import get_folders

router = APIRouter(prefix="/api/mail", tags=["mail-folders"])


class FolderCreate(BaseModel):
    name: str


class FolderRename(BaseModel):
    new_name: str


class FolderMove(BaseModel):
    new_parent: str  # Empty string = move to root level


@router.get("/folders")
async def list_folders(request: Request, username: str = Depends(get_current_user)):
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        folders = await get_folders(imap)
        return {"folders": folders}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.post("/folders")
async def create_folder(body: FolderCreate, request: Request, username: str = Depends(get_current_user)):
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        imap_name = _imap_utf7_encode(body.name)
        resp = await imap.create(imap_name)
        if resp.result != "OK":
            raise HTTPException(status_code=400, detail=f"Failed to create folder: {body.name}")
        await imap.subscribe(imap_name)
        return {"status": "created", "name": body.name}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.put("/folders/{folder_name:path}")
async def rename_folder(folder_name: str, body: FolderRename, request: Request, username: str = Depends(get_current_user)):
    """Renombrar carpeta IMAP. El frontend envía el nuevo nombre COMPLETO (con path).
    Ej: renombrar INBOX.Camaras a INBOX.Cámaras → new_name='INBOX.Cámaras'
    """
    if body.new_name == folder_name:
        return {"status": "unchanged", "name": folder_name}
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        old_encoded = _imap_utf7_encode(folder_name)
        new_encoded = _imap_utf7_encode(body.new_name)
        # CRÍTICO: aioimaplib pasa argumentos raw al socket IMAP.
        # SIEMPRE quotear para que nombres con espacios/especiales sean un solo token.
        old_q = '"' + old_encoded.replace('\\', '\\\\').replace('"', '\\"') + '"'
        new_q = '"' + new_encoded.replace('\\', '\\\\').replace('"', '\\"') + '"'
        logger.info(f"RENAME: {folder_name!r} -> {body.new_name!r} | imap: {old_q} -> {new_q}")
        resp = await imap.rename(old_q, new_q)
        logger.info(f"RENAME result: {resp.result} {resp.lines}")
        if resp.result != "OK":
            imap_err = resp.lines[0] if resp.lines else "unknown"
            logger.error(f"RENAME FAILED: {imap_err}")
            raise HTTPException(status_code=400, detail=f"IMAP RENAME error: {imap_err}")
        try:
            await imap.subscribe(new_q)
        except Exception:
            pass
        return {"status": "renamed", "old_name": folder_name, "new_name": body.new_name}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.post("/folders/move")
async def move_folder(body: FolderMove, request: Request, folder_name: str = "", username: str = Depends(get_current_user)):
    """Move a folder under a new parent. Uses IMAP RENAME to relocate."""
    # This endpoint is called as POST /api/mail/folders/move with JSON body
    # containing folder_name and new_parent
    pass


@router.post("/folders/{folder_name:path}/move")
async def move_folder_named(folder_name: str, body: FolderMove, request: Request, username: str = Depends(get_current_user)):
    """Move a folder under a new parent. Uses IMAP RENAME to relocate."""
    protected = {"INBOX", "Sent", "Drafts", "Trash", "Junk", "Archive"}
    if folder_name in protected:
        raise HTTPException(status_code=400, detail="No se puede mover una carpeta del sistema")

    # Extract base name (last segment after dot)
    base_name = folder_name.rsplit(".", 1)[-1] if "." in folder_name else folder_name

    # Build new full name
    if body.new_parent:
        new_full_name = f"{body.new_parent}.{base_name}"
    else:
        new_full_name = base_name

    if new_full_name == folder_name:
        return {"status": "unchanged", "name": folder_name}

    # No mover una carpeta dentro de sí misma (IMAP rechaza esto)
    if new_full_name.startswith(folder_name + "."):
        raise HTTPException(status_code=400, detail="No se puede mover una carpeta dentro de sí misma")

    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        old_imap = _imap_utf7_encode(folder_name)
        new_imap = _imap_utf7_encode(new_full_name)
        # CRÍTICO: aioimaplib pasa los argumentos de RENAME directamente al socket IMAP.
        # Si el nombre tiene espacios, IMAP lo interpreta como tokens separados.
        # SIEMPRE quotear con comillas dobles para que IMAP lo trate como un solo argumento.
        old_q = '"' + old_imap.replace('"', '\\"') + '"'
        new_q = '"' + new_imap.replace('"', '\\"') + '"'
        logger.info(f"MOVE: old_q={old_q!r} new_q={new_q!r}")
        resp = await imap.rename(old_q, new_q)
        logger.info(f"MOVE result: {resp.result} lines={resp.lines}")
        if resp.result != "OK":
            imap_err = resp.lines[0] if resp.lines else "unknown"
            logger.error(f"MOVE FAILED: {imap_err}")
            raise HTTPException(status_code=400, detail=f"IMAP RENAME error: {imap_err}")
        try:
            await imap.subscribe(new_q)
        except Exception:
            pass  # subscribe failure is non-critical
        return {"status": "moved", "old_name": folder_name, "new_name": new_full_name}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.delete("/folders/{folder_name:path}")
async def delete_folder(folder_name: str, request: Request, username: str = Depends(get_current_user)):
    protected = {"INBOX", "Sent", "Drafts", "Trash", "Junk", "Archive"}
    if folder_name in protected:
        raise HTTPException(status_code=400, detail="Cannot delete system folder")
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        imap_name = _imap_utf7_encode(folder_name)
        await imap.unsubscribe(imap_name)
        resp = await imap.delete(imap_name)
        if resp.result != "OK":
            raise HTTPException(status_code=400, detail="Failed to delete folder")
        return {"status": "deleted", "name": folder_name}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
