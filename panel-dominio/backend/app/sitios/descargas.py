"""Entrega de descargas del sitio (archivos, copias, informe de visitas) con un enlace de un solo uso.

El portal no puede leer lo que maquita-sitios prepara en su carpeta (ni debe: ahí están también las descargas
del panel general). El intermediario root la hace del usuario del portal y la deja en la carpeta de subidas del
portal con un nombre nuevo al azar (<32 hex>.descarga, 128 bits); la orden autenticada devuelve un enlace con ese
nombre. Al pedirlo, el archivo se reclama con un rename atómico (nadie más puede bajarlo), se envía por trozos
(sin cargarlo en memoria, aunque sea una copia de varios GB) y se borra al terminar. Pasados VIGENCIA segundos
sin pedirlo, caduca.

El enlace no lleva la ficha de sesión (el navegador lo abre como una descarga normal): lo protege que solo lo
conoce quien hizo la orden y que vale una vez.

El informe HTML de GoAccess se sirve con «Content-Security-Policy: sandbox»: corre en un origen opaco, sin
acceso a la sesión del portal aunque los registros traigan algo malicioso.
"""

import contextlib
import os
import re
import time
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.sitios import config

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
VIGENCIA = 600
# Una descarga lenta (satélite) puede tardar horas; lo reclamado se borra al terminar y, si se cortó, pasado un día.
VIGENCIA_ENTREGANDO = 86400
RE_DESCARGA = re.compile(r"[0-9a-f]{32}\.descarga")
RE_ENTREGANDO = re.compile(r"[0-9a-f]{32}\.descarga\.\d+\.entregando")
CSP_INFORME = ("sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
               "img-src data:; font-src data:; frame-ancestors 'none'")


def _nombre(nombre) -> str:
    return re.sub(r"[^\w.\- ]", "_", os.path.basename(str(nombre or "")))[:150].strip() or "descarga"


def _ruta(nombre: str) -> str:
    return os.path.join(config.DIR_SUBIDAS, nombre)


def _borrar(ruta: str) -> None:
    with contextlib.suppress(OSError):
        os.remove(ruta)


def limpiar_viejas() -> None:
    """Lo que nadie pidió a tiempo (o una entrega que se cortó) no se queda en la carpeta."""
    ahora = time.time()
    try:
        nombres = os.listdir(config.DIR_SUBIDAS)
    except OSError:
        return
    for n in nombres:
        vigencia = VIGENCIA if RE_DESCARGA.fullmatch(n) else VIGENCIA_ENTREGANDO if RE_ENTREGANDO.fullmatch(n) else None
        if vigencia is None:
            continue
        with contextlib.suppress(OSError):
            if ahora - os.lstat(_ruta(n)).st_mtime > vigencia:
                os.remove(_ruta(n))


def enlace(datos, ver: bool = False) -> dict:
    """Respuesta del intermediario ({descarga, nombre, bytes}) ⇒ {enlace, nombre, bytes} para el navegador."""
    descarga = datos.get("descarga") if isinstance(datos, dict) else None
    if not isinstance(descarga, str) or not RE_DESCARGA.fullmatch(descarga):
        raise HTTPException(502, "Respuesta no válida del servicio de sitios web")
    limpiar_viejas()
    nombre = _nombre(datos.get("nombre"))
    url = f"/api/sitios/descargas/{descarga}?nombre={quote(nombre)}" + ("&ver=1" if ver else "")
    return {"enlace": url, "nombre": nombre, "bytes": datos.get("bytes"), "vence_en_s": VIGENCIA}


@router.get("/descargas/{archivo}")
async def descargar(archivo: str, nombre: str = "descarga", ver: bool = False):
    if not RE_DESCARGA.fullmatch(archivo):
        raise HTTPException(404, "Enlace no válido")
    ruta = _ruta(archivo)
    reclamado = f"{ruta}.{os.getpid()}.entregando"
    try:
        info = os.lstat(ruta)
        if not os.path.isfile(ruta) or os.path.islink(ruta):
            raise HTTPException(404, "Enlace no válido")
        if time.time() - info.st_mtime > VIGENCIA:
            _borrar(ruta)
            raise HTTPException(410, "El enlace caducó: vuelve a pedir la descarga")
        os.rename(ruta, reclamado)
    except FileNotFoundError:
        raise HTTPException(410, "El enlace ya se usó o caducó: vuelve a pedir la descarga")
    nombre = _nombre(nombre)
    cabeceras = {"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
    tarea = BackgroundTask(_borrar, reclamado)
    if ver and nombre.lower().endswith(".html"):
        cabeceras["Content-Security-Policy"] = CSP_INFORME
        return FileResponse(reclamado, media_type="text/html; charset=utf-8", headers=cabeceras,
                            content_disposition_type="inline", filename=nombre, background=tarea)
    cabeceras["Content-Security-Policy"] = "sandbox; default-src 'none'"
    return FileResponse(reclamado, media_type="application/octet-stream", filename=nombre, headers=cabeceras,
                        background=tarea)
