"""OnlyOffice integration — convert Office files to PDF for preview."""
import logging
import jwt
import time
import json
import mimetypes
import asyncio
import hashlib
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password, get_imap_login_user
from app.mail.clients.imap_client import get_imap_connection, fetch_attachment
from app.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mail", tags=["mail-onlyoffice"])

_OO_SECRET = settings.onlyoffice_secret
_OO_URL = settings.onlyoffice_url
_DOWNLOAD_SECRET = settings.onlyoffice_download_secret


async def _oo_cfg(request):
    """Lee onlyoffice_url/secret de la tabla office_config (configurada en el
    panel). Si no hay fila habilitada o falla, usa los valores del .env."""
    url, secret = _OO_URL, _OO_SECRET
    try:
        row = await request.app.state.db_pool.fetchrow(
            "SELECT onlyoffice_url, onlyoffice_secret, enabled FROM office_config WHERE id = 1")
        if row and row["enabled"]:
            url = row["onlyoffice_url"] or url
            secret = row["onlyoffice_secret"] or secret
    except Exception:
        pass
    return url, secret

_OFFICE_EXT = {
    "docx", "doc", "odt", "rtf", "txt",
    "xlsx", "xls", "ods", "csv",
    "pptx", "ppt", "odp",
}


class OfficePreviewRequest(BaseModel):
    folder: str
    uid: int
    part_number: str
    filename: str


def _convert_to_pdf(convert_payload: dict) -> bytes:
    """Blocking call to OnlyOffice ConvertService — runs in thread pool."""
    req = urllib.request.Request(
        f"{_OO_URL}/ConvertService.ashx",
        data=json.dumps(convert_payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    result = resp.read().decode()
    logger.info("OnlyOffice response: %s", result[:200])

    root = ET.fromstring(result)
    error_el = root.find("Error")
    if error_el is not None and error_el.text != "0":
        raise ValueError(f"OnlyOffice error code: {error_el.text}")
    file_url_el = root.find("FileUrl")
    if file_url_el is None or not file_url_el.text:
        raise ValueError("No FileUrl in response")

    pdf_resp = urllib.request.urlopen(file_url_el.text, timeout=30)
    pdf_data = pdf_resp.read()
    logger.info("PDF downloaded: %d bytes", len(pdf_data))
    return pdf_data


@router.post("/office-preview")
async def office_preview(
    body: OfficePreviewRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Convert an Office attachment to PDF via OnlyOffice and return the PDF."""
    logger.info("office_preview called: %s %s", username, body.filename)

    ext = body.filename.rsplit(".", 1)[-1].lower() if "." in body.filename else ""
    if ext not in _OFFICE_EXT:
        raise HTTPException(status_code=400, detail=f"Extension '{ext}' not supported")

    dl_token = jwt.encode(
        {
            "sub": username,
            "folder": body.folder,
            "uid": body.uid,
            "part": body.part_number,
            "filename": body.filename,
            "exp": int(time.time()) + 3600,
        },
        _DOWNLOAD_SECRET,
        algorithm="HS256",
    )

    download_url = f"https://{settings.cookie_domain}/api/mail/oo-download?token={dl_token}"
    # Key must be alphanumeric — OnlyOffice rejects keys with @ or special chars
    key_hash = hashlib.md5(f"{username}_{body.folder}_{body.uid}_{body.part_number}".encode()).hexdigest()[:16]
    doc_key = f"pv_{key_hash}_{int(time.time())}"

    convert_payload = {
        "async": False,
        "filetype": ext,
        "key": doc_key,
        "outputtype": "pdf",
        "url": download_url,
    }
    convert_token = jwt.encode(convert_payload, _OO_SECRET, algorithm="HS256")
    convert_payload["token"] = convert_token

    try:
        loop = asyncio.get_event_loop()
        pdf_data = await loop.run_in_executor(None, _convert_to_pdf, convert_payload)
    except Exception as e:
        logger.error("Conversion failed: %s: %s", type(e).__name__, e)
        raise HTTPException(status_code=502, detail=f"Conversion failed: {e}")

    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{body.filename}.pdf"',
            "Cache-Control": "private, max-age=300",
        },
    )



class OfficeEditorRequest(BaseModel):
    folder: str
    uid: int
    part_number: str
    filename: str


@router.post("/office-editor-config")
async def office_editor_config(
    body: OfficeEditorRequest,
    request: Request,
    username: str = Depends(get_current_user),
):
    ext = body.filename.rsplit(".", 1)[-1].lower() if "." in body.filename else ""
    if ext not in _OFFICE_EXT:
        raise HTTPException(status_code=400, detail=f"Extension not supported: {ext}")

    dl_token = jwt.encode(
        {
            "sub": username,
            "folder": body.folder,
            "uid": body.uid,
            "part": body.part_number,
            "filename": body.filename,
            "exp": int(time.time()) + 3600,
        },
        _DOWNLOAD_SECRET,
        algorithm="HS256",
    )

    download_url = f"https://{settings.cookie_domain}/api/mail/oo-download?token={dl_token}"
    key_hash = hashlib.md5(f"{username}_{body.folder}_{body.uid}_{body.part_number}".encode()).hexdigest()[:16]
    doc_key = f"view_{key_hash}_{int(time.time())}"

    doc_type_map = {
        "docx": "word", "doc": "word", "odt": "word", "rtf": "word", "txt": "word",
        "xlsx": "cell", "xls": "cell", "ods": "cell", "csv": "cell",
        "pptx": "slide", "ppt": "slide", "odp": "slide",
    }
    doc_type = doc_type_map.get(ext, "word")

    editor_config = {
        "document": {
            "fileType": ext,
            "key": doc_key,
            "title": body.filename,
            "url": download_url,
            "permissions": {
                "edit": False,
                "download": True,
                "print": True,
                "comment": False,
                "review": False,
            },
        },
        "documentType": doc_type,
        "editorConfig": {
            "mode": "view",
            "lang": "es",
            "callbackUrl": f"https://{settings.cookie_domain}/api/mail/oo-callback",
            "customization": {
                "compactToolbar": True,
                "hideRightMenu": True,
                "toolbarNoTabs": True,
                "chat": False,
                "comments": False,
                "help": False,
                "about": False,
            },
        },
    }

    _oo_url, _oo_secret = await _oo_cfg(request)
    token = jwt.encode(editor_config, _oo_secret, algorithm="HS256")
    editor_config["token"] = token

    return editor_config


@router.get("/oo-download")
async def onlyoffice_download(
    token: str = Query(...),
    request: Request = None,
):
    """Download endpoint for OnlyOffice — authenticated via temporary JWT."""
    try:
        payload = jwt.decode(token, _DOWNLOAD_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    username = payload["sub"]
    folder = payload["folder"]
    uid = payload["uid"]
    part_number = payload["part"]
    filename = payload["filename"]

    # IMPORTANTE: Las contraseñas en Redis están cifradas con Fernet.
    # SIEMPRE usar get_user_password() — NUNCA redis.get() directo.
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

        return Response(
            content=data,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.post("/oo-callback")
async def onlyoffice_callback():
    """Dummy callback for OnlyOffice."""
    return {"error": 0}
