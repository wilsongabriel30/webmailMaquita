"""Entrega de lo que el ayudante deja en subidas/ para descargar (archivos del sitio, copias, informe de visitas).

El ayudante (root) escribe <32 hex>.descarga en /var/lib/maquita-sitios/subidas; la orden autenticada del panel
devuelve un enlace de un solo uso con ese nombre (128 bits al azar, válido VIGENCIA segundos). Al pedirlo, el
archivo se reclama con un rename atómico (nadie más puede bajarlo) y se borra al terminar de enviarlo. Así el
navegador descarga directamente, sin cargar en memoria copias de varios GB.

El informe HTML se sirve con «Content-Security-Policy: sandbox»: corre en un origen opaco, sin acceso a la
sesión del panel aunque los registros traigan algo malicioso.
"""

import os
import re
import time
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
SUBIDAS = "/var/lib/maquita-sitios/subidas"
VIGENCIA = 600
RE_DESCARGA = re.compile(r"^[0-9a-f]{32}\.descarga$")


def enlace(archivo: str, nombre: str, ver: bool = False) -> str:
    if not RE_DESCARGA.match(archivo or ""):
        raise HTTPException(500, "respuesta no válida del ayudante de sitios")
    return f"/api/sitios/descargas/{archivo}?nombre={quote(_nombre(nombre))}" + ("&ver=1" if ver else "")


def _nombre(nombre: str) -> str:
    limpio = re.sub(r"[^\w.\- ]", "_", os.path.basename(nombre or ""))[:150].strip() or "descarga"
    return limpio


def _borrar(ruta: str) -> None:
    try:
        os.remove(ruta)
    except OSError:
        pass


@router.get("/descargas/{archivo}")
async def descargar(archivo: str, nombre: str = "descarga", ver: bool = False):
    if not RE_DESCARGA.match(archivo):
        raise HTTPException(404, "Enlace no válido")
    ruta = os.path.join(SUBIDAS, archivo)
    reclamado = ruta + f".{os.getpid()}.entregando"
    try:
        if time.time() - os.lstat(ruta).st_mtime > VIGENCIA:
            _borrar(ruta)
            raise HTTPException(410, "El enlace caducó: vuelva a pedir la descarga")
        os.rename(ruta, reclamado)
    except FileNotFoundError:
        raise HTTPException(410, "El enlace ya se usó o caducó: vuelva a pedir la descarga")
    nombre = _nombre(nombre)
    cabeceras = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}
    if ver and nombre.lower().endswith(".html"):
        cabeceras["Content-Security-Policy"] = "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; " \
                                               "style-src 'unsafe-inline'; img-src data:; font-src data:"
        return FileResponse(reclamado, media_type="text/html; charset=utf-8", headers=cabeceras,
                            content_disposition_type="inline", filename=nombre, background=BackgroundTask(_borrar, reclamado))
    return FileResponse(reclamado, media_type="application/octet-stream", filename=nombre, headers=cabeceras,
                        background=BackgroundTask(_borrar, reclamado))
