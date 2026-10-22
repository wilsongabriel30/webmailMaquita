"""Autenticación de git de un sitio (repositorios privados), en el panel general: la del despliegue de los sitios PHP y
la de las aplicaciones propias (deploy/sitios/lib/git_clave.py y git_credencial.py).

Métodos: clave de despliegue generada en el servidor (recomendada, de solo lectura), clave SSH propia, token de acceso
por HTTPS, usuario y contraseña por HTTPS, o ninguno (repositorio público). El secreto no viaja en los argumentos de
sudo (se verían con «ps» y quedarían en su registro): va en un archivo 0600 de subidas/ que maquita-sitios lee y
borra. No vuelve nunca en la respuesta y a la auditoría va solo el método.
"""

import json
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
SUBIDAS = "/var/lib/maquita-sitios/subidas"
METODOS = ("clave-generada", "clave-propia", "token-https", "usuario-contrasena", "ninguna")


class Credencial(BaseModel):
    metodo: str
    repo: str | None = None
    clave_privada: str | None = None
    token: str | None = None
    usuario: str | None = None
    contrasena: str | None = None
    regenerar: bool = False


def _dejar(datos: dict) -> str:
    nombre = secrets.token_hex(16) + ".cred"
    with open(os.open(os.path.join(SUBIDAS, nombre), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as f:
        json.dump(datos, f, ensure_ascii=False)
    return nombre


@router.get("/{dominio}/git/credencial")
async def estado(dominio: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("git-credencial", _dominio(dominio))


@router.put("/{dominio}/git/credencial")
async def guardar(dominio: str, body: Credencial, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if body.metodo not in METODOS:
        raise HTTPException(400, "Método de autenticación no válido")
    datos = {k: v for k, v in body.model_dump().items() if v not in (None, "")}
    if len(json.dumps(datos)) > 32 * 1024:
        raise HTTPException(400, "Datos demasiado largos")
    nombre = _dejar(datos)
    ruta = os.path.join(SUBIDAS, nombre)
    try:
        res = await _ayudante("git-credencial-guardar", dominio, nombre, tiempo=130)
    finally:
        if os.path.lexists(ruta):  # maquita-sitios la borra al leerla; si no llegó a hacerlo, aquí
            os.remove(ruta)
    await _auditar(r, admin, "sitio_git_credencial", dominio, {"metodo": body.metodo})
    return res


@router.delete("/{dominio}/git/credencial")
async def borrar(dominio: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("git-credencial-borrar", dominio)
    await _auditar(r, admin, "sitio_git_credencial_borrar", dominio)
    return res
