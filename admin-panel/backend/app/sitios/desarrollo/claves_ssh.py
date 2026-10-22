"""Claves SSH de las cuentas SFTP de un sitio (la principal y las adicionales), cada una en su encierro.

Solo claves públicas ed25519, ECDSA o RSA de 3072 bits o más (el ayudante las comprueba con ssh-keygen). En la
auditoría queda la huella, no la clave.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.dns.ayudante import b64
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_CUENTA = re.compile(r"principal|[a-z][a-z0-9]{1,10}")
RE_ID = re.compile(r"[0-9a-f]{8}")


class NuevaClave(BaseModel):
    cuenta: str = "principal"
    clave: str


@router.get("/{dominio}/ssh/claves")
async def listar(dominio: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("ssh-claves", _dominio(dominio), tiempo=120)


@router.post("/{dominio}/ssh/claves", status_code=201)
async def agregar(dominio: str, body: NuevaClave, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    clave = (body.clave or "").strip()
    if not RE_CUENTA.fullmatch(body.cuenta or ""):
        raise HTTPException(400, "Cuenta no válida")
    if not clave or len(clave) > 5000 or "\n" in clave or "\r" in clave:
        raise HTTPException(400, "Pega una sola clave pública (el contenido del archivo .pub), en una línea")
    res = await _ayudante("ssh-clave-agregar", dominio, body.cuenta, b64(clave), tiempo=120)
    agregada = (res or {}).get("agregada") or {}
    await _auditar(r, admin, "sitio_ssh_clave_agregar", dominio,
                   {"cuenta": body.cuenta, "tipo": agregada.get("tipo"), "huella": agregada.get("huella")})
    return res


@router.delete("/{dominio}/ssh/claves/{ident}")
async def borrar(dominio: str, ident: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if not RE_ID.fullmatch(ident or ""):
        raise HTTPException(400, "Clave no válida")
    res = await _ayudante("ssh-clave-borrar", dominio, ident, tiempo=120)
    await _auditar(r, admin, "sitio_ssh_clave_borrar", dominio, {"id": ident})
    return res
