"""Subir un paquete propio (.zip, .tar.gz, .rar o .7z) a un sitio vacío; con el respaldo de su base (.sql o .sql.gz) es una
migración desde otro hosting (se importa la base y se conecta la aplicación).

Los archivos se guardan por trozos en /var/lib/maquita-sitios/subidas con un nombre aleatorio (nunca el que trae)
y el ayudante root los comprueba, los usa y los borra. Máximo 512 MB entre los dos.
"""

import os
import re
import secrets

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.auth.dependencies import require_superadmin
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
SUBIDAS = "/var/lib/maquita-sitios/subidas"
TOPE = 512 * 1048576


async def _guardar(subida: UploadFile, extensiones: tuple[str, ...], ya: int) -> tuple[str, int]:
    nombre = (subida.filename or "").lower()
    extension = next((e for e in extensiones if nombre.endswith(e)), None)
    if not extension:
        raise HTTPException(400, f"Formato no admitido: {subida.filename} (use {' o '.join(extensiones)})")
    destino = os.path.join(SUBIDAS, secrets.token_hex(16) + extension)
    total = ya
    try:
        with open(destino, "xb") as f:
            os.chmod(destino, 0o640)
            while bloque := await subida.read(1 << 20):
                total += len(bloque)
                if total > TOPE:
                    raise HTTPException(413, "Lo subido supera 512 MB")
                f.write(bloque)
    except BaseException:
        if os.path.exists(destino):
            os.remove(destino)
        raise
    return destino, total


@router.post("/{dominio}/paquete")
async def subir(dominio: str, r: Request, archivo: UploadFile = File(...), base: UploadFile | None = File(None),
                con_bd: bool = Form(False), admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if not os.path.isdir(SUBIDAS):
        raise HTTPException(503, "Falta la carpeta de subidas: actualice la sección de sitios (instalar-app.sh sitios)")
    destino, total = await _guardar(archivo, (".tar.gz", ".tgz", ".zip", ".rar", ".7z"), 0)
    destino_base = None
    try:
        if base is not None and base.filename:
            destino_base, total = await _guardar(base, (".sql.gz", ".sql"), total)
    except BaseException:
        os.remove(destino)
        raise
    args = ["paquete", dominio, os.path.basename(destino), "con-bd" if con_bd or destino_base else "sin-bd"]
    if destino_base:
        args.append(os.path.basename(destino_base))
    # El ayudante borra los archivos al terminar, haya salido bien o no.
    res = await _ayudante(*args, tiempo=1800)
    limpio = lambda s: re.sub(r"[^\w.\- ]", "", s.filename or "")[:120]  # noqa: E731
    await _auditar(r, admin, "sitio_migracion" if destino_base else "sitio_paquete", dominio,
                   {"archivo": limpio(archivo), "base": limpio(base) if destino_base else None,
                    "mb": round(total / 1048576, 1), "aplicacion": (res.get("migracion") or {}).get("aplicacion")})
    return res
