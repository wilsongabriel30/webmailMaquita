import re
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password
from app.mail.imap_service import (
    delete_message,
    get_imap_connection,
    get_message,
    list_folders,
    list_messages,
    move_message,
    set_flags,
)
from app.mail.smtp_service import send_email
from app.mail.utils import sanitize_html


def _validate_folder(folder: str) -> str:
    """Reject folder names with control characters (CRLF injection prevention)."""
    if re.search(r'[-]', folder):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Nombre de carpeta inválido")
    return folder


router = APIRouter(prefix="/api/mail", tags=["mail"])


class ComposeRequest(BaseModel):
    to: list[str]
    subject: str
    sensitivity: str = ""
    html_body: str = ""
    text_body: str = ""
    cc: list[str] | None = None
    bcc: list[str] | None = None
    in_reply_to: str = ""
    references: str = ""


class MoveRequest(BaseModel):
    dest_folder: str


class FlagRequest(BaseModel):
    flags: str
    add: bool = True


async def _get_user_imap(request: Request, username: str):
    """Get an IMAP connection for the current user using cached credentials."""
    password = await get_user_password(request, username)
    return await get_imap_connection(username, password)


@router.get("/folders")
async def get_folders(request: Request, username: str = Depends(get_current_user)):
    imap = await _get_user_imap(request, username)
    try:
        folders = await list_folders(imap)
        return {"folders": folders}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.get("/messages/{folder}")
async def get_messages(
    folder: str,
    request: Request,
    page: int = 1,
    per_page: int = 50,
    username: str = Depends(get_current_user),
):
    if per_page > 100:
        per_page = 100
    folder = _validate_folder(folder)
    imap = await _get_user_imap(request, username)
    try:
        result = await list_messages(imap, folder, page, per_page)
        return result
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.get("/message/{folder}/{seq}")
async def read_message(
    folder: str,
    seq: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    folder = _validate_folder(folder)
    imap = await _get_user_imap(request, username)
    try:
        msg = await get_message(imap, folder, seq)
        if msg is None:
            raise HTTPException(status_code=404, detail="Message not found")

        # Sanitize HTML body
        if msg.get("html_body"):
            msg["html_body"] = sanitize_html(msg["html_body"])

        return msg
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.post("/send")
async def send(
    body: ComposeRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    password = await get_user_password(request, username)

    result = await send_email(
        username=username,
        password=password,
        to=body.to,
        subject=body.subject,
        html_body=body.html_body,
        text_body=body.text_body,
        cc=body.cc,
        bcc=body.bcc,
        in_reply_to=body.in_reply_to,
        references=body.references,
    )
    return result


@router.post("/move/{folder}/{seq}")
async def move(
    folder: str,
    seq: int,
    body: MoveRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    imap = await _get_user_imap(request, username)
    try:
        folder = _validate_folder(folder)
        body.dest_folder = _validate_folder(body.dest_folder)
        ok = await move_message(imap, folder, seq, body.dest_folder)
        if not ok:
            raise HTTPException(status_code=400, detail="Failed to move message")
        return {"status": "moved"}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.post("/flags/{folder}/{seq}")
async def update_flags(
    folder: str,
    seq: int,
    body: FlagRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    imap = await _get_user_imap(request, username)
    try:
        folder = _validate_folder(folder)
        ok = await set_flags(imap, folder, seq, body.flags, body.add)
        if not ok:
            raise HTTPException(status_code=400, detail="Failed to update flags")
        return {"status": "updated"}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.delete("/message/{folder}/{seq}")
async def remove_message(
    folder: str,
    seq: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    imap = await _get_user_imap(request, username)
    try:
        folder = _validate_folder(folder)
        ok = await delete_message(imap, folder, seq)
        if not ok:
            raise HTTPException(status_code=400, detail="Failed to delete message")
        return {"status": "deleted"}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
