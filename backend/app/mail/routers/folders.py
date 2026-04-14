"""Folders router — list, create, rename, delete, move folders."""
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password, get_imap_login_user
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
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        old_imap = _imap_utf7_encode(folder_name)
        new_imap = _imap_utf7_encode(body.new_name)
        resp = await imap.rename(old_imap, new_imap)
        if resp.result != "OK":
            raise HTTPException(status_code=400, detail="Failed to rename folder")
        await imap.subscribe(new_imap)
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

    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        old_imap = _imap_utf7_encode(folder_name)
        new_imap = _imap_utf7_encode(new_full_name)
        resp = await imap.rename(old_imap, new_imap)
        if resp.result != "OK":
            raise HTTPException(status_code=400, detail=f"No se pudo mover la carpeta: {folder_name}")
        await imap.subscribe(new_imap)
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
