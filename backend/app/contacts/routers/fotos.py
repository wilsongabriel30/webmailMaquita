"""Fotos de perfil del directorio (05/11/2026) — capa genérica, para cualquier organización.

GET    /api/contacts/foto            estado de la foto propia (url y si la gestiona la nómina)
GET    /api/contacts/foto/{email}    sirve la foto guardada (solo con sesión; nunca pública)
POST   /api/contacts/foto            sube la propia (JPG/PNG/WebP ≤ 5 MB → WebP 256×256)
DELETE /api/contacts/foto            la quita

Donde un conector de nómina (Raíces en Maquita, app/tareas/jefes.py) tiene foto de la persona,
esa manda: el conector deja `user_profiles.photo_url` apuntando a la intranet y `fuente='nomina'`.
Las fotos se guardan FUERA del árbol de código (datos personales): /var/lib/maquita-webmail/fotos.
"""

import hashlib
import io
import os
import time

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

DIR_FOTOS = os.getenv("FOTOS_PERFIL_DIR", "/var/lib/maquita-webmail/fotos")
MAX_BYTES = 5 * 1024 * 1024
LADO = 256


def ruta_foto(email: str) -> str:
    return os.path.join(
        DIR_FOTOS,
        hashlib.sha1(email.strip().lower().encode("utf-8")).hexdigest() + ".webp",
    )


def _url_propia(email: str) -> str:
    return f"/api/contacts/foto/{email.strip().lower()}?v={int(time.time())}"


async def _estado(db, email: str) -> dict:
    fila = await db.fetchrow(
        "SELECT COALESCE(photo_url,'') AS photo_url, fuente, COALESCE(display_name,'') AS display_name "
        "FROM user_profiles WHERE lower(user_email) = lower($1)",
        email,
    )
    url = fila["photo_url"] if fila else ""
    gestiona_nomina = bool(
        fila and fila["fuente"] == "nomina" and url.startswith("http")
    )
    return {
        "photo_url": url,
        "la_gestiona_nomina": gestiona_nomina,
        "display_name": fila["display_name"] if fila else "",
    }


@router.get("/foto")
async def mi_foto(request: Request, username: str = Depends(get_current_user)):
    return await _estado(request.app.state.db_pool, username)


@router.get("/foto/{email}")
async def ver_foto(email: str, username: str = Depends(get_current_user)):
    p = ruta_foto(email)
    if not os.path.isfile(p):
        raise HTTPException(404, "Sin foto")
    return FileResponse(
        p, media_type="image/webp", headers={"Cache-Control": "private, max-age=3600"}
    )


@router.post("/foto")
async def subir_foto(
    request: Request,
    archivo: UploadFile = File(...),
    username: str = Depends(get_current_user),
):
    datos = await archivo.read()
    if len(datos) > MAX_BYTES:
        raise HTTPException(413, "La imagen pesa más de 5 MB")
    try:
        from PIL import Image, ImageOps

        im = Image.open(io.BytesIO(datos))
        im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "No es una imagen válida (JPG, PNG o WebP)")
    w, h = im.size
    lado = min(w, h)
    im = im.crop(
        (
            (w - lado) // 2,
            (h - lado) // 2,
            (w - lado) // 2 + lado,
            (h - lado) // 2 + lado,
        )
    )
    im = im.resize((LADO, LADO), Image.LANCZOS)
    os.makedirs(DIR_FOTOS, exist_ok=True)
    destino = ruta_foto(username)
    im.save(destino + ".tmp", "WEBP", quality=82)
    os.replace(destino + ".tmp", destino)

    db = request.app.state.db_pool
    estado = await _estado(db, username)
    if estado["la_gestiona_nomina"]:
        # La foto institucional viene de la nómina: se guarda la propia pero no sustituye a esa.
        return {
            "ok": True,
            "photo_url": estado["photo_url"],
            "la_gestiona_nomina": True,
        }
    url = _url_propia(username)
    await db.execute(
        """INSERT INTO user_profiles (user_email, photo_url, fuente) VALUES ($1, $2, 'propio')
           ON CONFLICT (user_email) DO UPDATE SET photo_url = EXCLUDED.photo_url,
               fuente = COALESCE(user_profiles.fuente, 'propio'), updated_at = NOW()""",
        username,
        url,
    )
    try:
        await request.app.state.redis.delete(f"avatar:{username.lower()}")
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "photo_url": url, "la_gestiona_nomina": False}


@router.delete("/foto")
async def quitar_foto(request: Request, username: str = Depends(get_current_user)):
    p = ruta_foto(username)
    if os.path.isfile(p):
        os.remove(p)
    db = request.app.state.db_pool
    estado = await _estado(db, username)
    if not estado["la_gestiona_nomina"]:
        await db.execute(
            "UPDATE user_profiles SET photo_url = '', updated_at = NOW() WHERE lower(user_email) = lower($1)",
            username,
        )
        try:
            await request.app.state.redis.delete(f"avatar:{username.lower()}")
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "la_gestiona_nomina": estado["la_gestiona_nomina"]}
