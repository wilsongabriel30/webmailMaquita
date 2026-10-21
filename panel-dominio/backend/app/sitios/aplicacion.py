"""Aplicación del sitio: instalar del catálogo, entrar sin contraseña, contraseña nueva del
administrador, revisar, actualizar y cerrar el instalador web.

Las contraseñas que se generan vuelven una sola vez en la respuesta, para mostrarlas en pantalla:
no se guardan ni se auditan.
"""

from fastapi import APIRouter, Depends, Request

from app.sesion import admin_actual
from app.sitios import validacion as v
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


@router.post("/{sitio}/app")
async def instalar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    datos = await cuerpo(request)
    args = {"aplicacion": v.aplicacion(datos.get("aplicacion")), "titulo": v.titulo(datos.get("titulo")),
            "correo": v.correo(datos.get("correo"))}
    return await llamar(request, admin, "app", sitio, args, "sitio_app", {"aplicacion": args["aplicacion"]})


@router.post("/{sitio}/entrar")
async def entrar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    """Enlace de un solo uso (60 s) al escritorio de la aplicación."""
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "entrar", sitio, {}, "sitio_entrar")


@router.post("/{sitio}/clave-admin")
async def clave_admin(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "clave-admin", sitio, {}, "sitio_clave_admin")


@router.post("/{sitio}/revisar")
async def revisar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    """Versión, actualizaciones pendientes e integridad del núcleo. Solo consulta: no se audita."""
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "revisar", sitio)


@router.post("/{sitio}/actualizar")
async def actualizar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "actualizar", sitio, {}, "sitio_actualizar")


@router.post("/{sitio}/terminar")
async def terminar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "terminar", sitio, {}, "sitio_app_terminar")
