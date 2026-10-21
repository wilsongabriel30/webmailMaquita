"""Guardar lo que se sube (paquetes, respaldos, archivos editados) en la carpeta del portal.

Por trozos y sin cargarlo entero en memoria; con un tope que se comprueba mientras llega (no se
fía del Content-Length). El nombre es siempre <32 hex>.<ext>, al azar, nunca el que trae el
archivo. El tipo se reconoce por los primeros bytes, no por el nombre. El intermediario abre el
archivo con O_NOFOLLOW, comprueba que es nuestro y lo mueve; lo que quede aquí se borra.
"""

import codecs
import contextlib
import os
import re
import secrets
import time

from fastapi import HTTPException, Request

from app.sitios import config

RE_SUBIDA = re.compile(r"^[0-9a-f]{32}\.(zip|tar\.gz|tgz|sql|sql\.gz|txt)$")
_PARCIAL = ".parcial"


def _extension(clase: str, cabeza: bytes) -> str | None:
    if clase == "paquete":
        if cabeza.startswith(b"PK\x03\x04"):
            return ".zip"
        if cabeza.startswith(b"\x1f\x8b"):
            return ".tar.gz"
        return None
    if clase == "respaldo":
        if cabeza.startswith(b"\x1f\x8b"):
            return ".sql.gz"
        return ".sql" if cabeza and b"\x00" not in cabeza else None
    return ".txt"


_FORMATO = {"paquete": "El paquete debe ser .zip o .tar.gz",
            "respaldo": "El respaldo de la base debe ser .sql o .sql.gz"}


def ruta(nombre: str) -> str:
    return os.path.join(config.DIR_SUBIDAS, nombre)


def quitar(nombre: str | None) -> None:
    """Borra una subida propia si sigue aquí (el intermediario la mueve al usarla)."""
    if nombre and RE_SUBIDA.match(nombre):
        with contextlib.suppress(FileNotFoundError):
            os.remove(ruta(nombre))


def existe(nombre: str) -> bool:
    """Que sea una subida con forma válida, un archivo normal (no un enlace) y reciente."""
    if not RE_SUBIDA.match(nombre or ""):
        return False
    try:
        info = os.lstat(ruta(nombre))
    except OSError:
        return False
    return os.path.isfile(ruta(nombre)) and not os.path.islink(ruta(nombre)) and \
        time.time() - info.st_mtime < config.MINUTOS_SUBIDA * 60


def limpiar_viejas() -> None:
    """Lo que nadie usó (una subida cortada, un respaldo sin paquete) no se queda para siempre."""
    limite = time.time() - config.MINUTOS_SUBIDA * 60
    try:
        nombres = os.listdir(config.DIR_SUBIDAS)
    except OSError:
        return
    for nombre in nombres:
        if not (RE_SUBIDA.match(nombre) or re.fullmatch(r"[0-9a-f]{32}" + re.escape(_PARCIAL), nombre)):
            continue
        with contextlib.suppress(OSError):
            if os.lstat(ruta(nombre)).st_mtime < limite:
                os.remove(ruta(nombre))


async def recibir(request: Request, clase: str, tope: int) -> tuple[str, int]:
    """Guarda el cuerpo de la petición. Devuelve (nombre, bytes). `clase`: paquete, respaldo o texto."""
    if not os.path.isdir(config.DIR_SUBIDAS):
        raise HTTPException(503, "Falta la carpeta de subidas del portal. Avisa al administrador general.")
    limpiar_viejas()
    try:
        if int(request.headers.get("content-length") or 0) > tope:
            raise HTTPException(413, demasiado(tope))
    except ValueError:
        raise HTTPException(400, "Petición no válida")
    base = secrets.token_hex(16)
    parcial = ruta(base + _PARCIAL)
    utf8 = codecs.getincrementaldecoder("utf-8")() if clase == "texto" else None
    total, cabeza, fd = 0, b"", None
    try:
        fd = os.open(parcial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        async for trozo in request.stream():
            if not trozo:
                continue
            total += len(trozo)
            if total > tope:
                raise HTTPException(413, demasiado(tope))
            if len(cabeza) < 16:
                cabeza += trozo[:16]
            if utf8:
                try:
                    utf8.decode(trozo)
                except UnicodeDecodeError:
                    raise HTTPException(400, "El archivo debe ser texto en UTF-8")
            vista = memoryview(trozo)
            while vista:
                vista = vista[os.write(fd, vista):]
        os.close(fd)
        fd = None
        if utf8:
            try:
                utf8.decode(b"", final=True)
            except UnicodeDecodeError:
                raise HTTPException(400, "El archivo debe ser texto en UTF-8")
        if total == 0 and clase != "texto":
            raise HTTPException(400, "No llegó ningún archivo")
        extension = _extension(clase, cabeza)
        if not extension:
            raise HTTPException(400, _FORMATO.get(clase, "Formato no admitido"))
        nombre = base + extension
        os.rename(parcial, ruta(nombre))
        return nombre, total
    except OSError:
        raise HTTPException(500, "No se pudo guardar lo subido. Avisa al administrador general.")
    finally:
        if fd is not None:
            os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            os.remove(parcial)


def demasiado(tope: int) -> str:
    if tope >= 1024 * 1024:
        return f"Lo subido supera {tope // (1024 * 1024)} MB"
    return f"El contenido supera {tope // 1024} KB"
