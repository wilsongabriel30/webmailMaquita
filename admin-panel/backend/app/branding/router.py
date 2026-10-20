import os
import shutil
import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.auth.dependencies import get_current_admin, require_superadmin

router = APIRouter(prefix="/api/branding", tags=["branding"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = "/opt/maquita-webmail/uploads/branding"


REDES = ("facebook", "instagram", "x", "youtube", "linkedin", "tiktok")


def _redes(valor) -> str:
    """Redes sociales como JSON {red: url https}; las vacías se descartan."""
    import json

    if isinstance(valor, str):
        try:
            valor = json.loads(valor or "{}")
        except ValueError:
            raise HTTPException(400, "Redes sociales no válidas")
    if not isinstance(valor, dict):
        raise HTTPException(400, "Redes sociales no válidas")
    limpio = {}
    for red, url in valor.items():
        url = str(url or "").strip()
        if not url:
            continue
        if red not in REDES or not url.startswith("https://") or len(url) > 200 or any(c in url for c in '<>" '):
            raise HTTPException(400, f"Enlace de {red} no válido (debe empezar por https://)")
        limpio[red] = url
    return json.dumps(limpio, ensure_ascii=False)


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
    # [H-02] Endpoint PUBLICO (lo usa la pantalla de entrada): solo nombre, lema, contacto,
    # colores y ficheros de marca. Nada de configuracion interna.
    _PUBLICAS = ('org_name', 'app_name', 'org_slogan', 'org_phone', 'org_email', 'org_website', 'primary_color', 'secondary_color', 'footer_text', 'logo_url', 'favicon_url',
                 'org_short', 'org_description', 'org_social')
    result = {r["key"]: r["value"] for r in rows if r["key"] in _PUBLICAS}

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
        "org_name", "app_name", "org_slogan", "org_email", "org_website",
        "org_phone", "primary_color", "footer_text",
        # Identidad completa (fase 3): nombre corto, descripción para buscadores e IA, redes sociales.
        "org_short", "org_description", "org_social",
    ]

    for key, value in body.items():
        if key not in allowed_keys:
            continue
        val = str(value).strip()
        if key == "org_social":
            val = _redes(value)
        elif key in ("org_short", "org_description"):
            limite = 30 if key == "org_short" else 300
            if len(val) > limite or any(ord(c) < 32 or c in '<>"' for c in val):
                raise HTTPException(400, f"{'Nombre corto' if key == 'org_short' else 'Descripción'}: hasta {limite} caracteres, sin < > ni comillas")
        if key == "app_name":
            # Es el nombre del producto: va al título, a los avisos y al emisor del segundo factor.
            if not 1 <= len(val) <= 60 or any(ord(c) < 32 or c in '<>"' for c in val):
                raise HTTPException(400, "El nombre del producto debe tener entre 1 y 60 caracteres, sin < > ni comillas")
        await db.execute("""
            INSERT INTO branding_settings (key, value, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
        """, key, val)
    from app import marca

    await marca.refrescar(db)
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


@router.post("/aplicar")
async def aplicar_identidad(request: Request, admin=Depends(require_superadmin)):
    """Aplica la identidad guardada en todo el servidor: app del correo (nombre e íconos), Drive,
    páginas «en construcción» de los sitios; reinicia webmail y Drive (guardan el nombre al arrancar)."""
    import json

    from app.dns.ayudante import auditar, ayudante, b64

    db = _db(request)
    await _ensure_table(db)
    filas = {r["key"]: r["value"] for r in await db.fetch("SELECT key, value FROM branding_settings")}
    if not (filas.get("org_name") or "").strip():
        raise HTTPException(400, "Primero guarde el nombre de la organización")
    try:
        redes = json.loads(filas.get("org_social") or "{}")
    except ValueError:
        redes = {}
    identidad = {
        "nombre": filas.get("org_name", ""),
        "corto": filas.get("org_short", ""),
        "app": filas.get("app_name", ""),
        "descripcion": filas.get("org_description", "") or filas.get("org_slogan", ""),
        "correo": filas.get("org_email", ""),
        "telefono": filas.get("org_phone", ""),
        "color": filas.get("primary_color", ""),
        "redes": redes,
    }
    res = await ayudante("identidad", "aplicar", b64(identidad), tiempo=300)
    await auditar(request, admin, "identidad_aplicar", identidad["nombre"], {"resultado": res})
    return res
