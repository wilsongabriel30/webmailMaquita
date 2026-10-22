"""CPU y memoria del sitio (últimas 24 horas) e información del servidor (v1.11).

La información del servidor es la que hace falta para configurar programas y saber qué ofrece el hospedaje:
versiones de PHP, rutas, IP compartida, servidores de nombres de tus dominios, cuotas, FTP/SFTP y correo. La
arma el intermediario, que no incluye nada de otros dominios ni datos internos del servidor.
"""

from fastapi import APIRouter, Depends, Request

from app.sesion import admin_actual
from app.sitios.comun import exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


@router.get("/servidor")
async def informacion(request: Request, admin: dict = Depends(admin_actual)):
    return await llamar(request, admin, "servidor-info")


@router.get("/{sitio}/recursos")
async def recursos(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "recursos", sitio)
