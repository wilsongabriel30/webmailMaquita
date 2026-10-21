"""Subidas del portal (paquetes, respaldos .sql, textos y archivos del sitio) hacia la carpeta de maquita-sitios.

El portal solo puede escribir en su carpeta (subidas-portal, suya y 0700). Lo que deja ahí no se cree:
se abre sin seguir enlaces (O_NOFOLLOW, relativo a la carpeta ya abierta), tiene que ser un archivo
normal, del usuario del portal y con un solo nombre (sin enlaces duros), y se COPIA desde ese mismo
descriptor a un archivo nuevo de root en subidas/. Así, aunque el portal cambie el nombre o el contenido
después de la comprobación, maquita-sitios trabaja con una copia que ya no puede tocar.
"""

import os
import pwd
import re
import secrets
import stat

import rutas
from errores import ErrorPortal

EXTENSIONES = {
    "paquete": re.compile(r"^[0-9a-f]{32}\.(zip|tar\.gz|tgz)$"),
    "respaldo": re.compile(r"^[0-9a-f]{32}\.(sql|sql\.gz)$"),
    "texto": re.compile(r"^[0-9a-f]{32}\.txt$"),
    # Administrador de archivos (v1.10): cualquier contenido; maquita-sitios lo copia con el usuario del sitio.
    "archivo": re.compile(r"^[0-9a-f]{32}\.subida$"),
}
TOPES = {"paquete": 512 * 1024 * 1024, "respaldo": 512 * 1024 * 1024, "texto": 1024 * 1024,
         "archivo": 512 * 1024 * 1024}
BLOQUE = 1024 * 1024


def _uid_portal():
    try:
        return pwd.getpwnam(rutas.USUARIO_PORTAL).pw_uid
    except KeyError:
        raise ErrorPortal(503, "El portal de dominio no está instalado en este servidor")


def tamano(nombre, tipo):
    """Tamaño en bytes de una subida (sin moverla), para comprobar la cuota antes."""
    fd = _abrir(nombre, tipo)
    try:
        return os.fstat(fd).st_size
    finally:
        os.close(fd)


def _abrir(nombre, tipo):
    if not isinstance(nombre, str) or not EXTENSIONES[tipo].fullmatch(nombre):
        raise ErrorPortal(400, "Archivo subido no válido")
    try:
        carpeta = os.open(rutas.SUBIDAS_PORTAL, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise ErrorPortal(503, "La carpeta de subidas del portal no existe")
    try:
        fd = os.open(nombre, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=carpeta)
    except OSError:
        raise ErrorPortal(400, "No llegó el archivo subido")
    finally:
        os.close(carpeta)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != _uid_portal() or st.st_nlink != 1:
        os.close(fd)
        raise ErrorPortal(400, "Archivo subido no válido")
    if st.st_size > TOPES[tipo]:
        os.close(fd)
        raise ErrorPortal(413, "El archivo es demasiado grande")
    return fd


def tomar(nombre, tipo):
    """Copia la subida a subidas/ con un nombre nuevo (root, 0600), borra la del portal y devuelve el nombre."""
    fd = _abrir(nombre, tipo)
    extension = nombre.split(".", 1)[1]
    nuevo = f"{secrets.token_hex(16)}.{extension}"
    destino = os.path.join(rutas.SUBIDAS, nuevo)
    copiado = 0
    try:
        with open(os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as salida:
            while True:
                trozo = os.read(fd, BLOQUE)
                if not trozo:
                    break
                copiado += len(trozo)
                if copiado > TOPES[tipo]:
                    raise ErrorPortal(413, "El archivo es demasiado grande")
                salida.write(trozo)
    except BaseException:
        if os.path.lexists(destino):
            os.remove(destino)
        raise
    finally:
        os.close(fd)
        quitar(nombre)
    return nuevo


def quitar(nombre):
    """Borra la subida del portal (siempre: se use o no)."""
    if isinstance(nombre, str) and any(r.fullmatch(nombre) for r in EXTENSIONES.values()):
        try:
            os.remove(os.path.join(rutas.SUBIDAS_PORTAL, nombre))
        except OSError:
            pass


def descartar(nuevo):
    """Borra una copia ya tomada que al final no se usó."""
    if nuevo and os.path.lexists(os.path.join(rutas.SUBIDAS, nuevo)):
        os.remove(os.path.join(rutas.SUBIDAS, nuevo))
