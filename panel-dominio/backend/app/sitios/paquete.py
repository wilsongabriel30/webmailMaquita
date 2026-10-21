"""Subir un paquete propio (.zip o .tar.gz) a un sitio vacío y, con el respaldo de su base, migrar
desde otro hospedaje.

Son dos subidas para no mezclar dos archivos grandes en una sola petición: primero el respaldo
(opcional), que devuelve su nombre, y después el paquete, que lo nombra y pone el trabajo en
marcha. El nombre del respaldo es al azar (32 hex) y solo lo conoce quien lo subió.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios import config, subidas
from app.sitios.comun import exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_RESPALDO = re.compile(r"^[0-9a-f]{32}\.(sql|sql\.gz)$")


def _nombre_original(valor) -> str | None:
    """Solo para la auditoría: el nombre que traía el archivo, sin nada raro."""
    return re.sub(r"[^\w.\- ]", "", str(valor or ""))[:120] or None


@router.put("/{sitio}/paquete/respaldo")
async def subir_respaldo(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    guardado, total = await subidas.recibir(request, "respaldo", config.SUBIDA_MAX_BYTES)
    return {"respaldo": guardado, "bytes": total}


@router.put("/{sitio}/paquete")
async def subir_paquete(sitio: str, request: Request, con_bd: int = 0, respaldo: str = "", nombre: str = "",
                        admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    if respaldo and not (RE_RESPALDO.match(respaldo) and subidas.existe(respaldo)):
        raise HTTPException(400, "El respaldo de la base ya no está: vuelve a subirlo")
    guardado, llamado = None, False
    try:
        guardado, total = await subidas.recibir(request, "paquete", config.SUBIDA_MAX_BYTES)
        llamado = True
        args = {"subida": guardado, "con_bd": bool(con_bd) or bool(respaldo)}
        if respaldo:
            args["respaldo"] = respaldo
        return await llamar(request, admin, "paquete", sitio, args,
                            "sitio_migracion" if respaldo else "sitio_paquete",
                            {"archivo": _nombre_original(nombre), "mb": round(total / 1048576, 1),
                             "con_bd": args["con_bd"], "con_respaldo": bool(respaldo)})
    finally:
        # El intermediario mueve lo que usa; si falló antes, no se deja nada aquí. Si lo que falló
        # fue el paquete (formato, tope), el respaldo se conserva para no subirlo otra vez.
        subidas.quitar(guardado)
        if llamado:
            subidas.quitar(respaldo or None)
