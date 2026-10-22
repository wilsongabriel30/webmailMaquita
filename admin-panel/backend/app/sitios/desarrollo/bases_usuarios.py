"""Usuarios adicionales de las bases de un sitio: permisos a medida, clave nueva, borrar y acceso remoto con TLS.

El ayudante (maquita-sitios) pone el nombre «u_<sitio>_<sufijo>», genera la contraseña (vuelve una sola vez: no se
guarda en el panel ni en la auditoría), aplica los permisos con identificadores comprobados y, para el acceso
remoto, crea las cuentas con REQUIRE SSL (MariaDB) o las líneas hostssl (PostgreSQL) y abre el puerto en el
cortafuegos solo para esas IP. Una red más amplia que /16 (IPv4) o /48 (IPv6) solo la puede autorizar el
superadministrador marcando «confirmar_amplia»; /0 nunca.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.dns.ayudante import b64
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_BASE = re.compile(r"[wx]_[a-z0-9]+(_[0-9a-f]{4})?")
RE_SUFIJO = re.compile(r"[a-z][a-z0-9]{1,9}")
RE_USUARIO = re.compile(r"u_[a-z0-9]+_[a-z][a-z0-9]{1,9}")
RE_PRIVILEGIO = re.compile(r"[A-Z][A-Z ]{2,30}")
PERFILES = ("lectura", "escritura", "estructura", "todo", "medida")


class Permisos(BaseModel):
    perfil: str
    lista: list[str] | None = None


class NuevoUsuario(BaseModel):
    base: str
    sufijo: str
    permisos: Permisos


class CambioPermisos(BaseModel):
    permisos: Permisos


class Remoto(BaseModel):
    redes: list[str]
    confirmar_amplia: bool = False


def _usuario(valor: str) -> str:
    if not RE_USUARIO.fullmatch(valor or ""):
        raise HTTPException(400, "Usuario no válido")
    return valor


def _permisos(p: Permisos) -> dict:
    if p.perfil not in PERFILES:
        raise HTTPException(400, "Permisos no válidos: lectura, escritura, estructura, todo o a medida")
    if p.perfil != "medida":
        return {"perfil": p.perfil}
    if not p.lista or len(p.lista) > 20 or not all(RE_PRIVILEGIO.fullmatch(x) for x in p.lista):
        raise HTTPException(400, "Elige al menos un permiso de la lista")
    return {"perfil": "medida", "lista": p.lista}


@router.get("/{dominio}/bases/usuarios")
async def listar(dominio: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("bases-usuarios", _dominio(dominio), tiempo=120)


@router.post("/{dominio}/bases/usuarios", status_code=201)
async def crear(dominio: str, body: NuevoUsuario, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if not RE_BASE.fullmatch(body.base or ""):
        raise HTTPException(400, "Base de datos no válida")
    if not RE_SUFIJO.fullmatch(body.sufijo or ""):
        raise HTTPException(400, "Nombre no válido: de 2 a 10 minúsculas o números, empezando por una letra")
    permisos = _permisos(body.permisos)
    res = await _ayudante("base-usuario-crear", dominio, body.base, body.sufijo, b64(permisos), tiempo=120)
    await _auditar(r, admin, "sitio_base_usuario_crear", dominio, {"base": body.base, "sufijo": body.sufijo, "permisos": permisos})
    return res


@router.put("/{dominio}/bases/usuarios/{usuario}/permisos")
async def permisos(dominio: str, usuario: str, body: CambioPermisos, r: Request, admin: dict = Depends(require_superadmin)):
    dominio, usuario, nuevos = _dominio(dominio), _usuario(usuario), _permisos(body.permisos)
    res = await _ayudante("base-usuario-permisos", dominio, usuario, b64(nuevos), tiempo=120)
    await _auditar(r, admin, "sitio_base_usuario_permisos", dominio, {"usuario": usuario, "permisos": nuevos})
    return res


@router.post("/{dominio}/bases/usuarios/{usuario}/clave")
async def nueva_clave(dominio: str, usuario: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio, usuario = _dominio(dominio), _usuario(usuario)
    res = await _ayudante("base-usuario-clave", dominio, usuario, tiempo=120)
    await _auditar(r, admin, "sitio_base_usuario_clave", dominio, {"usuario": usuario})
    return res


@router.put("/{dominio}/bases/usuarios/{usuario}/remoto")
async def remoto(dominio: str, usuario: str, body: Remoto, r: Request, admin: dict = Depends(require_superadmin)):
    dominio, usuario = _dominio(dominio), _usuario(usuario)
    redes = [x.strip() for x in body.redes if x and x.strip()]
    if len(redes) > 20 or any(len(x) > 50 for x in redes):
        raise HTTPException(400, "Se admiten hasta 20 IP o redes por usuario")
    # «amplia» la decide el superadministrador, y solo con una sesión abierta con segundo factor (no con una ficha).
    amplia = body.confirmar_amplia and admin["role"] == "superadmin" and bool(admin.get("totp"))
    args = ["base-usuario-remoto", dominio, usuario, b64(redes)] + (["amplia"] if amplia else [])
    res = await _ayudante(*args, tiempo=120)
    await _auditar(r, admin, "sitio_base_usuario_remoto", dominio, {"usuario": usuario, "redes": redes, "amplia": amplia})
    return res


@router.delete("/{dominio}/bases/usuarios/{usuario}")
async def borrar(dominio: str, usuario: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio, usuario = _dominio(dominio), _usuario(usuario)
    res = await _ayudante("base-usuario-borrar", dominio, usuario, tiempo=120)
    await _auditar(r, admin, "sitio_base_usuario_borrar", dominio, {"usuario": usuario})
    return res
