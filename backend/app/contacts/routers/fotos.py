"""Fotos de perfil del directorio (05/11/2026) — capa genérica, para cualquier organización.

GET    /api/contacts/foto            estado: photo_url (efectiva), foto_raices_url, foto_propia_url, origen_actual,
                                     la_gestiona_nomina (hay foto en Raíces)
GET    /api/contacts/foto/{email}    sirve la foto guardada (solo con sesión; nunca pública)
POST   /api/contacts/foto            sube la propia (JPG/PNG/WebP ≤ 5 MB → WebP 256×256)
DELETE /api/contacts/foto            quita la propia y vuelve a la de Raíces (si existe)

Regla «la foto de Raíces manda» (09/11/2026, REGLA-WEBMAIL-FOTO-PERFIL-RAICES-MANDA): el conector de
nómina (app/tareas/jefes.py) guarda la foto de Raíces en `foto_raices_url` (+ huella). La persona puede
subir una propia desde aquí (`foto_propia_url`), que pasa a ser la EFECTIVA (`photo_url`, la que leen todas
las vistas) hasta que la foto de Raíces cambie: en ese momento el conector la pisa. La decisión está en
app/contacts/foto_efectiva.py. Las fotos se guardan FUERA del árbol de código: /var/lib/maquita-webmail/fotos.
"""

import hashlib
import io
import os
import time

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.auth.dependencies import get_current_user
from app.contacts.foto_efectiva import (
    Cambios,
    EstadoFoto,
    al_quitar_propia,
    al_subir_propia,
)

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

DIR_FOTOS = os.getenv("FOTOS_PERFIL_DIR", "/var/lib/maquita-webmail/fotos")
MAX_BYTES = 5 * 1024 * 1024
LADO = 256


def ruta_foto(email: str) -> str:
    return os.path.join(
        DIR_FOTOS,
        hashlib.sha1(
            email.strip().lower().encode("utf-8"), usedforsecurity=False
        ).hexdigest()
        + ".webp",
    )


def _url_propia(email: str) -> str:
    return f"/api/contacts/foto/{email.strip().lower()}?v={int(time.time())}"


async def _leer(db, email: str) -> tuple[EstadoFoto, str]:
    fila = await db.fetchrow(
        "SELECT COALESCE(photo_url,'') AS photo_url, COALESCE(foto_raices_url,'') AS foto_raices_url, "
        "COALESCE(foto_raices_huella,'') AS foto_raices_huella, COALESCE(foto_propia_url,'') AS foto_propia_url, "
        "COALESCE(foto_origen,'') AS foto_origen, COALESCE(display_name,'') AS display_name "
        "FROM user_profiles WHERE lower(user_email) = lower($1)",
        email,
    )
    if not fila:
        return EstadoFoto(), ""
    return (
        EstadoFoto(
            photo_url=fila["photo_url"],
            foto_raices_url=fila["foto_raices_url"],
            foto_raices_huella=fila["foto_raices_huella"],
            foto_propia_url=fila["foto_propia_url"],
            foto_origen=fila["foto_origen"],
        ),
        fila["display_name"],
    )


def _respuesta(estado: EstadoFoto, display_name: str = "") -> dict:
    hay_raices = estado.foto_raices_url.startswith("http")
    origen = estado.foto_origen or (
        "nomina" if hay_raices and estado.photo_url == estado.foto_raices_url else ""
    )
    return {
        "photo_url": estado.photo_url,
        "foto_raices_url": estado.foto_raices_url,
        "foto_propia_url": estado.foto_propia_url,
        "origen_actual": origen,
        # Hay foto en Raíces: la propia (si se pone) vale hasta que esa cambie.
        "la_gestiona_nomina": hay_raices,
        "display_name": display_name,
    }


async def _aplicar(request: Request, email: str, c: Cambios) -> None:
    """Escribe los cambios decididos e invalida la caché `avatar:<correo>` si la efectiva cambió."""
    if c.vacio():
        return
    await request.app.state.db_pool.execute(
        """INSERT INTO user_profiles (user_email, photo_url, foto_raices_url, foto_raices_huella, foto_propia_url,
                                      foto_origen, fuente, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, 'propio', NOW())
           ON CONFLICT (user_email) DO UPDATE SET photo_url = EXCLUDED.photo_url,
               foto_raices_url = EXCLUDED.foto_raices_url, foto_raices_huella = EXCLUDED.foto_raices_huella,
               foto_propia_url = EXCLUDED.foto_propia_url, foto_origen = EXCLUDED.foto_origen,
               fuente = COALESCE(user_profiles.fuente, 'propio'), updated_at = NOW()""",
        email,
        c.photo_url,
        c.foto_raices_url,
        c.foto_raices_huella,
        c.foto_propia_url,
        c.foto_origen,
    )
    if c.invalidar_cache:
        try:
            await request.app.state.redis.delete(f"avatar:{email.lower()}")
        except Exception:  # noqa: BLE001
            pass


async def _estado(db, email: str) -> dict:
    estado, nombre = await _leer(db, email)
    return _respuesta(estado, nombre)


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
    estado, nombre = await _leer(db, username)
    # La propia pasa a ser la efectiva para todos; si la foto de Raíces cambia después, el conector la pisa.
    cambios = al_subir_propia(estado, _url_propia(username))
    await _aplicar(request, username, cambios)
    nuevo, _ = await _leer(db, username)
    return {"ok": True, **_respuesta(nuevo, nombre)}


@router.delete("/foto")
async def quitar_foto(request: Request, username: str = Depends(get_current_user)):
    p = ruta_foto(username)
    if os.path.isfile(p):
        os.remove(p)
    db = request.app.state.db_pool
    estado, nombre = await _leer(db, username)
    # Vuelve a la foto de Raíces si la hay; si no, se queda sin foto.
    await _aplicar(request, username, al_quitar_propia(estado))
    nuevo, _ = await _leer(db, username)
    return {"ok": True, **_respuesta(nuevo, nombre)}
