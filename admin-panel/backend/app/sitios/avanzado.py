"""Configuración avanzada de un sitio: reglas propias de nginx, ajustes de PHP y archivos de la aplicación, con
copia automática antes de cada cambio (la hace el ayudante) y la vuelta a cualquier versión anterior.

«Copiar sin contraseñas» devuelve el texto con los secretos tachados, para consultarlo fuera del servidor.
"""

import base64
import os
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import require_superadmin
from app.dns.ayudante import b64
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
SUBIDAS = "/var/lib/maquita-sitios/subidas"
TOPE = 1024 * 1024


def _dejar(texto: str) -> str:
    """El contenido viaja al ayudante por un archivo (no cabe como argumento de sudo)."""
    datos = texto.encode()
    if len(datos) > TOPE:
        raise HTTPException(413, "El contenido supera 1 MB")
    nombre = secrets.token_hex(16) + ".txt"
    with open(os.open(os.path.join(SUBIDAS, nombre), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640), "wb") as f:
        f.write(datos)
    return nombre


def _ruta(valor: str) -> str:
    valor = (valor or "").strip().lstrip("/")
    if not valor or ".." in valor.split("/") or len(valor) > 300 or re.search(r"[\x00-\x1f]", valor):
        raise HTTPException(400, "Ruta no válida")
    return base64.urlsafe_b64encode(valor.encode()).decode().rstrip("=")


@router.get("/{dominio}/avanzado")
async def ver(dominio: str, admin: dict = Depends(require_superadmin)):
    return await _ayudante("avanzado", _dominio(dominio))


class Texto(BaseModel):
    contenido: str


@router.put("/{dominio}/avanzado/nginx")
async def guardar_nginx(dominio: str, body: Texto, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("avanzado-nginx", dominio, _dejar(body.contenido))
    await _auditar(r, admin, "sitio_avanzado_nginx", dominio, {"bytes": len(body.contenido)})
    return res


@router.put("/{dominio}/avanzado/php")
async def guardar_php(dominio: str, body: dict, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("avanzado-php", dominio, b64(body))
    await _auditar(r, admin, "sitio_avanzado_php", dominio, body)
    return res


@router.get("/{dominio}/avanzado/archivo")
async def ver_archivo(dominio: str, ruta: str, admin: dict = Depends(require_superadmin)):
    return await _ayudante("avanzado-ver", _dominio(dominio), _ruta(ruta))


class Archivo(BaseModel):
    ruta: str
    contenido: str


@router.put("/{dominio}/avanzado/archivo")
async def guardar_archivo(dominio: str, body: Archivo, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("avanzado-archivo", dominio, _ruta(body.ruta), _dejar(body.contenido))
    await _auditar(r, admin, "sitio_avanzado_archivo", dominio, {"ruta": body.ruta, "bytes": len(body.contenido)})
    return res


@router.post("/{dominio}/avanzado/restaurar/{version}")
async def restaurar(dominio: str, version: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if not re.fullmatch(r"\d{8}-\d{6}-\d{3}", version):
        raise HTTPException(400, "Versión no válida")
    res = await _ayudante("avanzado-restaurar", dominio, version)
    await _auditar(r, admin, "sitio_avanzado_restaurar", dominio, {"version": version})
    return res


# --- Copiar sin contraseñas ---

# Valores secretos que no deben salir del servidor.
_SECRETOS = [
    re.compile(r"""(define\(\s*['"](?:DB_PASSWORD|AUTH_KEY|SECURE_AUTH_KEY|LOGGED_IN_KEY|NONCE_KEY|AUTH_SALT|"""
               r"""SECURE_AUTH_SALT|LOGGED_IN_SALT|NONCE_SALT|[A-Z_]*(?:PASS|SECRET|KEY|TOKEN|SALT)[A-Z_]*)['"]\s*,\s*['"])[^'"]*""", re.I),
    re.compile(r"""((?:public\s+)?\$(?:password|secret|smtppass|key)\s*=\s*['"])[^'"]*""", re.I),
    re.compile(r"""(^\s*[A-Z0-9_]*(?:PASS|PASSWORD|SECRET|KEY|TOKEN|SALT)[A-Z0-9_]*\s*=\s*)\S+""", re.I | re.M),
    re.compile(r"""(['"](?:password|pass|secret|key|token)['"]\s*=>\s*['"])[^'"]*""", re.I),
]


def tachar(texto: str) -> str:
    for patron in _SECRETOS:
        texto = patron.sub(lambda m: m.group(1) + "***", texto)
    return texto


class Tachar(BaseModel):
    contenido: str


@router.post("/{dominio}/avanzado/copia")
async def copia_sin_secretos(dominio: str, body: Tachar, admin: dict = Depends(require_superadmin)):
    """El texto con contraseñas, claves y secretos tachados: para consultarlo con otra persona o con una herramienta
    externa sin exponerlos. No se envía a ningún sitio: vuelve al navegador."""
    _dominio(dominio)
    if len(body.contenido) > TOPE:
        raise HTTPException(413, "El contenido supera 1 MB")
    return {"contenido": tachar(body.contenido)}
