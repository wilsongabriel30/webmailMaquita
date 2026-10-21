"""Privacidad de directorios: usuario y contraseña por carpeta del sitio.

La contraseña la pone la persona o la genera el ayudante; en ese caso se devuelve una sola vez. Nunca se guarda
en el panel ni en la auditoría (el ayudante solo guarda su cifrado bcrypt en la carpeta privada del sitio).
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import require_superadmin
from app.sitios.router import _auditar, _ayudante, _dominio
from app.sitios.web.comun import b64_corto

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_USUARIO = re.compile(r"^[A-Za-z0-9._-]{1,32}$")


def _usuario(valor: str) -> str:
    if not RE_USUARIO.fullmatch(valor or ""):
        raise HTTPException(400, "Usuario no válido (letras sin tilde, números y . _ -, hasta 32)")
    return valor


class Acceso(BaseModel):
    carpeta: str
    usuario: str
    clave: str | None = None


@router.post("/{dominio}/web/privacidad")
async def agregar(dominio: str, body: Acceso, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    args = ["web-privado-agregar", dominio, b64_corto(body.carpeta.strip(), "Carpeta"), _usuario(body.usuario)]
    if body.clave:
        if not 8 <= len(body.clave) <= 128:
            raise HTTPException(400, "La contraseña debe tener entre 8 y 128 caracteres")
        args.append(b64_corto(body.clave, "Contraseña"))
    res = await _ayudante(*args)
    await _auditar(r, admin, "sitio_web_privado_agregar", dominio, {"carpeta": body.carpeta, "usuario": body.usuario})
    return res


@router.delete("/{dominio}/web/privacidad")
async def quitar(dominio: str, carpeta: str, r: Request, usuario: str | None = None, admin: dict = Depends(require_superadmin)):
    """Sin usuario, quita la protección de la carpeta entera."""
    dominio = _dominio(dominio)
    args = ["web-privado-quitar", dominio, b64_corto(carpeta.strip(), "Carpeta")] + ([_usuario(usuario)] if usuario else [])
    res = await _ayudante(*args)
    await _auditar(r, admin, "sitio_web_privado_quitar", dominio, {"carpeta": carpeta, "usuario": usuario})
    return res
