import os
import shutil
import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/branding", tags=["branding"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = "/opt/maquita-webmail/uploads/branding"


def _db(request: Request):
    return request.app.state.db


async def _ensure_table(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS branding_settings (
            key VARCHAR(100) PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)


@router.get("")
async def get_branding(request: Request):
    db = _db(request)
    await _ensure_table(db)
    rows = await db.fetch("SELECT key, value FROM branding_settings")
    result = {r["key"]: r["value"] for r in rows}

    # Add file URLs if files exist
    for ftype in ("favicon", "logo"):
        path = os.path.join(UPLOAD_DIR, ftype)
        if os.path.isdir(path):
            files = os.listdir(path)
            if files:
                result[f"{ftype}_url"] = f"/api/branding/file/{ftype}/{files[0]}"

    return result


@router.put("")
async def update_branding(request: Request, admin=Depends(get_current_admin)):
    db = _db(request)
    await _ensure_table(db)
    body = await request.json()

    allowed_keys = [
        "org_name", "org_slogan", "org_email", "org_website",
        "org_phone", "primary_color", "footer_text",
    ]

    for key, value in body.items():
        if key not in allowed_keys:
            continue
        val = str(value).strip()
        await db.execute("""
            INSERT INTO branding_settings (key, value, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
        """, key, val)

    return {"success": True}


@router.post("/upload/{file_type}")
async def upload_file(
    file_type: str,
    request: Request,
    file: UploadFile = File(...),
    admin=Depends(get_current_admin),
):
    if file_type not in ("favicon", "logo"):
        raise HTTPException(400, "Tipo debe ser 'favicon' o 'logo'")

    # Validate file
    if not file.content_type or not file.content_type.startswith("image/"):
        # Allow .ico for favicon
        if file_type == "favicon" and file.content_type == "image/x-icon":
            pass
        elif file_type == "favicon" and (file.filename or "").endswith(".ico"):
            pass
        elif not (file.content_type or "").startswith("image/"):
            raise HTTPException(400, "Solo se permiten archivos de imagen")

    # Max 2MB
    contents = await file.read()
    if len(contents) > 2 * 1024 * 1024:
        raise HTTPException(400, "Archivo demasiado grande (max 2MB)")

    # Save file
    dest_dir = os.path.join(UPLOAD_DIR, file_type)
    os.makedirs(dest_dir, exist_ok=True)

    # Remove old files
    for old in os.listdir(dest_dir):
        os.remove(os.path.join(dest_dir, old))

    # Save with original extension
    ext = os.path.splitext(file.filename or "file.png")[1] or ".png"
    safe_name = f"{file_type}{ext}"
    filepath = os.path.join(dest_dir, safe_name)

    with open(filepath, "wb") as f:
        f.write(contents)

    logger.info(f"Branding: {file_type} uploaded by {admin['username']} ({len(contents)} bytes)")

    return {"success": True, "url": f"/api/branding/file/{file_type}/{safe_name}"}


@router.get("/file/{file_type}/{filename}")
async def get_file(file_type: str, filename: str):
    if file_type not in ("favicon", "logo"):
        raise HTTPException(404)

    # Sanitize filename
    safe = os.path.basename(filename)
    filepath = os.path.join(UPLOAD_DIR, file_type, safe)

    if not os.path.isfile(filepath):
        raise HTTPException(404, "Archivo no encontrado")

    return FileResponse(filepath)


@router.delete("/file/{file_type}")
async def delete_file(file_type: str, request: Request, admin=Depends(get_current_admin)):
    if file_type not in ("favicon", "logo"):
        raise HTTPException(400)

    dest_dir = os.path.join(UPLOAD_DIR, file_type)
    if os.path.isdir(dest_dir):
        for f in os.listdir(dest_dir):
            os.remove(os.path.join(dest_dir, f))

    logger.info(f"Branding: {file_type} deleted by {admin['username']}")
    return {"success": True}
