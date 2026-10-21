"""Órdenes del administrador de archivos (lado root): cargan el sitio, preparan las subidas y descargas y pasan
cada operación al usuario del sitio (como_usuario.ejecutar_como). La raíz es siempre la carpeta pública.

Subir: el panel deja el archivo en SUBIDAS (<32 hex>.subida); root lo abre, el hijo lo copia y root lo borra.
Descargar: root crea <32 hex>.descarga en SUBIDAS (el grupo del panel lo hereda de la carpeta), el hijo escribe
en él y el panel lo entrega autenticado y lo borra; lo que quede de más de un día lo borra «datos-noche».
"""

import os
import re
import secrets

import archivos
import archivos_papelera as papelera
import archivos_zip
from como_usuario import ejecutar_como
from comun import ErrorSitio, leer_meta

SUBIDAS = "/var/lib/maquita-sitios/subidas"
RE_SUBIDA = re.compile(r"^[0-9a-f]{32}\.subida$")


def _sitio(dominio):
    meta = leer_meta(dominio)
    if not os.path.isdir(meta["publico"]):
        raise ErrorSitio("el sitio no tiene carpeta pública")
    return meta


def _como(meta, funcion, *args):
    return ejecutar_como(meta["usuario"], funcion, *args)


def listar(dominio, ruta):
    meta = _sitio(dominio)
    return {"dominio": dominio, **_como(meta, archivos.listar, meta["publico"], ruta)}


def subir(dominio, ruta, subida, reemplazar=False):
    if not RE_SUBIDA.fullmatch(subida or ""):
        raise ErrorSitio("subida no válida")
    origen = os.path.join(SUBIDAS, subida)
    try:
        meta = _sitio(dominio)
        try:
            fd = os.open(origen, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            raise ErrorSitio("no se encontró el archivo subido")
        try:
            return _como(meta, archivos.subir, meta["publico"], ruta, fd, reemplazar)
        finally:
            os.close(fd)
    finally:
        if os.path.lexists(origen):
            os.remove(origen)


def descargar(dominio, ruta):
    meta = _sitio(dominio)
    nombre = secrets.token_hex(16) + ".descarga"
    destino = os.path.join(SUBIDAS, nombre)
    fd = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
    try:
        datos = _como(meta, archivos.descargar, meta["publico"], ruta, fd)
    except BaseException:
        os.close(fd)
        os.remove(destino)
        raise
    os.close(fd)
    return {"dominio": dominio, "archivo": nombre, **datos}


def carpeta(dominio, ruta):
    meta = _sitio(dominio)
    return _como(meta, archivos.carpeta, meta["publico"], ruta)


def mover(dominio, origen, destino):
    meta = _sitio(dominio)
    return _como(meta, archivos.mover, meta["publico"], origen, destino)


def copiar(dominio, origen, destino):
    meta = _sitio(dominio)
    return _como(meta, archivos.copiar, meta["publico"], origen, destino)


def permisos(dominio, ruta, modo):
    meta = _sitio(dominio)
    return _como(meta, archivos.permisos, meta["publico"], ruta, modo)


def comprimir(dominio, datos):
    if not isinstance(datos, dict) or not isinstance(datos.get("destino"), str):
        raise ErrorSitio("datos no válidos")
    meta = _sitio(dominio)
    return _como(meta, archivos_zip.comprimir, meta["publico"], datos.get("rutas"), datos["destino"])


def descomprimir(dominio, archivo, destino):
    meta = _sitio(dominio)
    return _como(meta, archivos_zip.descomprimir, meta["publico"], archivo, destino)


def borrar(dominio, ruta):
    meta = _sitio(dominio)
    return _como(meta, papelera.borrar, meta["publico"], papelera.ruta(meta), ruta)


def ver_papelera(dominio):
    meta = _sitio(dominio)
    return {"dominio": dominio, **_como(meta, papelera.listar, papelera.ruta(meta))}


def recuperar(dominio, ident):
    meta = _sitio(dominio)
    return _como(meta, papelera.recuperar, meta["publico"], papelera.ruta(meta), ident)


def vaciar(dominio):
    meta = _sitio(dominio)
    return _como(meta, papelera.vaciar, papelera.ruta(meta))


def purgar(meta):
    """Cada noche: lo que lleva más de 30 días en la papelera (con el usuario del sitio)."""
    if not os.path.isdir(papelera.ruta(meta)):
        return 0
    return _como(meta, papelera.vaciar, papelera.ruta(meta), papelera.DIAS)["vaciados"]
