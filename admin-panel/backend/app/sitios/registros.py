"""Visor de registros del sitio: últimas líneas de los errores y accesos de nginx y de los errores de PHP.

El ayudante solo lee tres archivos fijos de la carpeta del sitio (ver deploy/sitios/lib/visor_registros.py);
aquí se elige el tipo, el número de líneas (tope 1000) y un filtro de texto simple.
"""

import re

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_superadmin
from app.dns.ayudante import b64
from app.sitios.router import _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
TIPOS = ("error", "acceso", "php")


@router.get("/{dominio}/registros/{tipo}")
async def ver(dominio: str, tipo: str, lineas: int = 200, filtro: str = "", admin: dict = Depends(require_superadmin)):
    if tipo not in TIPOS:
        raise HTTPException(400, "Registro no válido")
    if not 1 <= lineas <= 1000:
        raise HTTPException(400, "Entre 1 y 1000 líneas")
    filtro = filtro.strip()
    # 140 bytes: en base64url caben en los 200 caracteres que admite maquita-sudo.
    if len(filtro) > 100 or len(filtro.encode()) > 140 or re.search(r"[\x00-\x1f\x7f]", filtro):
        raise HTTPException(400, "Filtro no válido (hasta 100 caracteres)")
    args = ["registros", _dominio(dominio), tipo, str(lineas)]
    if filtro:
        args.append(b64(filtro))
    return await _ayudante(*args)
