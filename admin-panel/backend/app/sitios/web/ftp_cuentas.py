"""Cuentas FTP adicionales de un sitio, cada una encerrada en una subcarpeta de la carpeta pública.

La cuenta principal sigue en router.py («/{dominio}/ftp»). La contraseña de una cuenta adicional se genera en el
servidor y se devuelve una sola vez: no se guarda en el panel ni en la auditoría.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.sitios.router import _auditar, _ayudante, _dominio
from app.sitios.web.comun import b64_corto

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_CUENTA = re.compile(r"^[a-z][a-z0-9]{1,10}$")


def _cuenta(valor: str) -> str:
    if not RE_CUENTA.fullmatch(valor or ""):
        raise HTTPException(400, "Nombre no válido: de 2 a 11 minúsculas o números, empezando por una letra")
    return valor


class NuevaCuenta(BaseModel):
    nombre: str
    carpeta: str


@router.get("/{dominio}/ftp/cuentas")
async def listar(dominio: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("ftp-cuentas", _dominio(dominio))


@router.post("/{dominio}/ftp/cuentas", status_code=201)
async def crear(dominio: str, body: NuevaCuenta, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    carpeta = body.carpeta.strip().strip("/")
    res = await _ayudante("ftp-cuenta-crear", dominio, _cuenta(body.nombre), b64_corto(carpeta, "Subcarpeta"))
    await _auditar(r, admin, "sitio_ftp_cuenta_crear", dominio, {"nombre": body.nombre, "carpeta": carpeta})
    return res


@router.post("/{dominio}/ftp/cuentas/{nombre}/clave")
async def nueva_clave(dominio: str, nombre: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("ftp-cuenta-clave", dominio, _cuenta(nombre))
    await _auditar(r, admin, "sitio_ftp_cuenta_clave", dominio, {"nombre": nombre})
    return res


@router.delete("/{dominio}/ftp/cuentas/{nombre}")
async def quitar(dominio: str, nombre: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("ftp-cuenta-quitar", dominio, _cuenta(nombre))
    await _auditar(r, admin, "sitio_ftp_cuenta_quitar", dominio, {"nombre": nombre})
    return res
