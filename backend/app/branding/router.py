import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/branding", tags=["branding"])

UPLOAD_DIR = "/opt/maquita-webmail/uploads/branding"


@router.get("")
async def get_branding(request: Request):
    db = request.app.state.db_pool
    try:
        rows = await db.fetch("SELECT key, value FROM branding_settings")
    except Exception:
        return {}
    result = {r["key"]: r["value"] for r in rows}

    # Nombre de organizacion para el frontend (TwoFactorGate, etc.), con fallback neutro
    result.setdefault("org_name", "Tu organización")

    for ftype in ("favicon", "logo"):
        path = os.path.join(UPLOAD_DIR, ftype)
        if os.path.isdir(path):
            files = os.listdir(path)
            if files:
                result[f"{ftype}_url"] = f"/api/branding/file/{ftype}/{files[0]}"

    return result


@router.get("/file/{file_type}/{filename}")
async def get_file(file_type: str, filename: str):
    if file_type not in ("favicon", "logo"):
        raise HTTPException(404)
    safe = os.path.basename(filename)
    filepath = os.path.join(UPLOAD_DIR, file_type, safe)
    if not os.path.isfile(filepath):
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(filepath)
