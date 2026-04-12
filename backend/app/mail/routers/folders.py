"""Folders router — list, create, rename, delete folders."""
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password, get_imap_login_user
from app.mail.clients.imap_client import get_imap_connection
from app.mail.services.folder_service import get_folders

router = APIRouter(prefix="/api/mail", tags=["mail-folders"])


class FolderCreate(BaseModel):
    name: str


class FolderRename(BaseModel):
    new_name: str


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
        resp = await imap.create(body.name)
        if resp.result != "OK":
            raise HTTPException(status_code=400, detail=f"Failed to create folder: {body.name}")
        await imap.subscribe(body.name)
        return {"status": "created", "name": body.name}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.put("/folders/{folder_name}")
async def rename_folder(folder_name: str, body: FolderRename, request: Request, username: str = Depends(get_current_user)):
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        resp = await imap.rename(folder_name, body.new_name)
        if resp.result != "OK":
            raise HTTPException(status_code=400, detail="Failed to rename folder")
        await imap.subscribe(body.new_name)
        return {"status": "renamed", "old_name": folder_name, "new_name": body.new_name}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.delete("/folders/{folder_name}")
async def delete_folder(folder_name: str, request: Request, username: str = Depends(get_current_user)):
    # Prevent deleting system folders
    protected = {"INBOX", "Sent", "Drafts", "Trash", "Junk", "Archive"}
    if folder_name in protected:
        raise HTTPException(status_code=400, detail="Cannot delete system folder")
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        await imap.unsubscribe(folder_name)
        resp = await imap.delete(folder_name)
        if resp.result != "OK":
            raise HTTPException(status_code=400, detail="Failed to delete folder")
        return {"status": "deleted", "name": folder_name}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
