"""Copias del sitio que controla su dueño (v1.10): crear ahora (archivos y bases), listar, descargar, restaurar
y borrar. Son aparte de los respaldos del servidor, que hace el administrador general.

Como mucho 5 por sitio; antes de restaurar se hace una copia previa automática del estado de ese momento. Las
copias cuentan para el espacio en disco del dominio: el intermediario comprueba la cuota antes de crear o
restaurar. La descarga va por un enlace de un solo uso (descargas.py).
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios import descargas
from app.sitios.comun import exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_COPIA = re.compile(r"\d{8}-\d{6}")


def _copia(valor: str) -> str:
    if not RE_COPIA.fullmatch(valor or ""):
        raise HTTPException(400, "Copia no válida")
    return valor


@router.get("/{sitio}/copias")
async def listar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "copias", sitio)


@router.post("/{sitio}/copias", status_code=201)
async def crear(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "copia-crear", sitio, None, "sitio_copia_crear")


@router.post("/{sitio}/copias/{copia}/descargar")
async def descargar(sitio: str, copia: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    copia = _copia(copia)
    datos = await llamar(request, admin, "copia-descargar", sitio, {"id": copia}, "sitio_copia_descargar", {"id": copia})
    return descargas.enlace(datos)


@router.post("/{sitio}/copias/{copia}/restaurar")
async def restaurar(sitio: str, copia: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    copia = _copia(copia)
    return await llamar(request, admin, "copia-restaurar", sitio, {"id": copia}, "sitio_copia_restaurar", {"id": copia})


@router.delete("/{sitio}/copias/{copia}")
async def borrar(sitio: str, copia: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    copia = _copia(copia)
    return await llamar(request, admin, "copia-borrar", sitio, {"id": copia}, "sitio_copia_borrar", {"id": copia})
