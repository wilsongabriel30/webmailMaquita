"""Certificado HTTPS (Let's Encrypt) y acceso FTP cifrado o SFTP del sitio."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios import validacion as v
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


@router.post("/{sitio}/https")
async def https(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    correo = v.correo((await cuerpo(request)).get("correo"))
    return await llamar(request, admin, "ssl", sitio, {"correo": correo}, "sitio_ssl")


@router.post("/{sitio}/ftp")
async def ftp(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    """«activar» también genera una clave nueva (vuelve una vez); la anterior deja de valer."""
    sitio, _ = exigir_sitio(admin, sitio)
    accion = str((await cuerpo(request)).get("accion") or "")
    if accion not in ("activar", "desactivar"):
        raise HTTPException(400, "Acción no válida")
    return await llamar(request, admin, "ftp", sitio, {"accion": accion}, f"sitio_ftp_{accion}")
