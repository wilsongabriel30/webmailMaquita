"""Claves SSH de las cuentas SFTP del sitio (v1.11): la principal y las adicionales, cada una en su encierro.

Se pega la clave PÚBLICA (ed25519, ECDSA o RSA de 3072 bits o más); maquita-sitios la comprueba con ssh-keygen y
devuelve su huella. Una clave de la cuenta principal solo vale mientras el acceso FTP/SFTP está activado.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual, auditar
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_CUENTA = re.compile(r"principal|[a-z][a-z0-9]{1,10}")
RE_ID = re.compile(r"[0-9a-f]{8}")


@router.get("/{sitio}/ssh/claves")
async def listar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "ssh-claves", sitio)


@router.post("/{sitio}/ssh/claves", status_code=201)
async def agregar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    datos = await cuerpo(request)
    cuenta = str(datos.get("cuenta") or "principal")
    clave = str(datos.get("clave") or "").strip()
    if not RE_CUENTA.fullmatch(cuenta):
        raise HTTPException(400, "Cuenta no válida")
    if not clave or len(clave) > 5000 or "\n" in clave or "\r" in clave:
        raise HTTPException(400, "Pega una sola clave pública (el contenido del archivo .pub), en una línea")
    r = await llamar(request, admin, "ssh-clave-agregar", sitio, {"cuenta": cuenta, "clave": clave})
    agregada = (r or {}).get("agregada") or {}
    await auditar(request, admin, "sitio_ssh_clave_agregar", sitio,
                  {"cuenta": cuenta, "tipo": agregada.get("tipo"), "huella": agregada.get("huella")})
    return r


@router.delete("/{sitio}/ssh/claves/{ident}")
async def borrar(sitio: str, ident: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    if not RE_ID.fullmatch(ident or ""):
        raise HTTPException(400, "Clave no válida")
    return await llamar(request, admin, "ssh-clave-borrar", sitio, {"id": ident}, "sitio_ssh_clave_borrar", {"id": ident})
