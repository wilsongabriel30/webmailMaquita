"""Cuentas FTP adicionales del sitio (v1.10): otra persona (un diseñador, un proveedor) entra por FTPS o SFTP
solo en una subcarpeta de la carpeta pública. La cuenta principal sigue en https_ftp.py.

La contraseña la genera el servidor y vuelve una sola vez en la respuesta: no se guarda en el portal ni en la
auditoría.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_CUENTA = re.compile(r"[a-z][a-z0-9]{1,10}")


def _cuenta(valor) -> str:
    valor = str(valor or "").strip()
    if not RE_CUENTA.fullmatch(valor):
        raise HTTPException(400, "Nombre no válido: de 2 a 11 minúsculas o números, empezando por una letra")
    return valor


@router.get("/{sitio}/ftp/cuentas")
async def listar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "ftp-cuentas", sitio)


@router.post("/{sitio}/ftp/cuentas", status_code=201)
async def crear(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    datos = await cuerpo(request)
    nombre, carpeta = _cuenta(datos.get("nombre")), str(datos.get("carpeta") or "").strip().strip("/")
    if not carpeta or len(carpeta) > 200:
        raise HTTPException(400, "Elige la subcarpeta de la carpeta pública a la que entrará la cuenta")
    return await llamar(request, admin, "ftp-cuenta-crear", sitio, {"nombre": nombre, "carpeta": carpeta},
                        "sitio_ftp_cuenta_crear", {"nombre": nombre, "carpeta": carpeta})


@router.post("/{sitio}/ftp/cuentas/{nombre}/clave")
async def nueva_clave(sitio: str, nombre: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    nombre = _cuenta(nombre)
    return await llamar(request, admin, "ftp-cuenta-clave", sitio, {"nombre": nombre}, "sitio_ftp_cuenta_clave", {"nombre": nombre})


@router.delete("/{sitio}/ftp/cuentas/{nombre}")
async def quitar(sitio: str, nombre: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    nombre = _cuenta(nombre)
    return await llamar(request, admin, "ftp-cuenta-quitar", sitio, {"nombre": nombre}, "sitio_ftp_cuenta_quitar", {"nombre": nombre})
