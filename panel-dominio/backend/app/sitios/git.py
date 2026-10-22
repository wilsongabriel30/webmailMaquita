"""Despliegue desde git del sitio PHP (v1.11): repositorio, rama, clave de despliegue, botón «Desplegar», gancho
con secreto para desplegar en cada push, registro y vuelta a una versión anterior.

El despliegue corre en segundo plano en el servidor: «Desplegar» vuelve enseguida y la pantalla consulta el
estado hasta que termina. El secreto del gancho vuelve UNA sola vez, al activarlo: no se audita ni se guarda aquí.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
CLAVES = ("repo", "rama", "carpeta", "raiz_web", "exclusiones")
RE_VERSION = re.compile(r"\d{8}-\d{6}")


@router.get("/{sitio}/git")
async def estado(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "git-estado", sitio)


@router.put("/{sitio}/git")
async def configurar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    datos = await cuerpo(request)
    if set(datos) - set(CLAVES) or not isinstance(datos.get("repo"), str):
        raise HTTPException(400, "Configuración no válida: repositorio, rama, carpetas y exclusiones")
    exclusiones = datos.get("exclusiones") or []
    if not isinstance(exclusiones, list) or len(exclusiones) > 20 or not all(isinstance(e, str) for e in exclusiones):
        raise HTTPException(400, "Se admiten hasta 20 archivos o carpetas que el despliegue no toca")
    git = {k: (str(datos.get(k) or "").strip()) for k in ("repo", "rama", "carpeta", "raiz_web")}
    git["exclusiones"] = [e.strip() for e in exclusiones if e.strip()]
    return await llamar(request, admin, "git-configurar", sitio, {"git": git}, "sitio_git_configurar",
                        {"repo": git["repo"], "rama": git["rama"]})


@router.post("/{sitio}/git/clave")
async def clave(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "git-clave", sitio, {}, "sitio_git_clave")


@router.post("/{sitio}/git/gancho")
async def gancho(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    accion = (await cuerpo(request)).get("accion")
    if accion not in ("activar", "desactivar"):
        raise HTTPException(400, "Acción no válida")
    return await llamar(request, admin, "git-gancho", sitio, {"accion": accion}, f"sitio_git_gancho_{accion}")


@router.post("/{sitio}/git/desplegar", status_code=202)
async def desplegar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "git-desplegar", sitio, {}, "sitio_git_desplegar")


@router.post("/{sitio}/git/volver")
async def volver(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    version = str((await cuerpo(request)).get("version") or "")
    if not RE_VERSION.fullmatch(version):
        raise HTTPException(400, "Versión no válida")
    return await llamar(request, admin, "git-volver", sitio, {"version": version}, "sitio_git_volver", {"version": version})


@router.delete("/{sitio}/git")
async def quitar(sitio: str, request: Request, confirmacion: str = "", admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    if confirmacion.strip().lower() != sitio:
        raise HTTPException(400, "Escribe el nombre del sitio para confirmar")
    return await llamar(request, admin, "git-quitar", sitio, {"confirmacion": sitio}, "sitio_git_quitar")
