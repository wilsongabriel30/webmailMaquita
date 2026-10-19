"""Subir un paquete propio (.zip o .tar.gz) a un sitio vacío.

El archivo se guarda por trozos en /var/lib/maquita-sitios/subidas con un nombre aleatorio (nunca el que trae)
y el ayudante root lo comprueba, lo extrae en el sitio y lo borra. Máximo 512 MB.
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


@router.post("/{dominio}/paquete")
async def subir(dominio: str, r: Request, archivo: UploadFile = File(...), con_bd: bool = Form(False),
                admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    nombre = (archivo.filename or "").lower()
    extension = next((e for e in (".tar.gz", ".tgz", ".zip") if nombre.endswith(e)), None)
    if not extension:
        raise HTTPException(400, "Suba un archivo .zip o .tar.gz")
    if not os.path.isdir(SUBIDAS):
        raise HTTPException(503, "Falta la carpeta de subidas: actualice la sección de sitios (instalar-app.sh sitios)")
    destino = os.path.join(SUBIDAS, secrets.token_hex(16) + extension)
    total = 0
    try:
        with open(destino, "xb") as f:
            os.chmod(destino, 0o640)
            while bloque := await archivo.read(1 << 20):
                total += len(bloque)
                if total > TOPE:
                    raise HTTPException(413, "El paquete supera 512 MB")
                f.write(bloque)
    except BaseException:
        if os.path.exists(destino):
            os.remove(destino)
        raise
    # El ayudante borra el archivo al terminar, haya salido bien o no.
    res = await _ayudante("paquete", dominio, os.path.basename(destino), "con-bd" if con_bd else "sin-bd", tiempo=900)
    await _auditar(r, admin, "sitio_paquete", dominio,
                   {"archivo": re.sub(r"[^\w.\- ]", "", archivo.filename or "")[:120], "mb": round(total / 1048576, 1),
                    "con_bd": con_bd})
    return res
