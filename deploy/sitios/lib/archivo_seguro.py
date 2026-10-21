"""Leer y escribir archivos de la carpeta de un sitio sin seguir enlaces simbólicos.

El ayudante corre como root y la carpeta del sitio es de su usuario, que entra por FTP o SFTP.
Comprobar la ruta con realpath y después abrirla por su nombre deja una ventana: entre las dos
cosas, el usuario puede cambiar un archivo o una carpeta por un enlace a /etc/shadow, y root
escribiría allí (2026-10-21, revisión de la v1.9). Aquí se abre cada componente desde el
descriptor de la carpeta anterior con O_NOFOLLOW, y todo lo demás (leer, crear el temporal,
dueño, permisos, renombrar) se hace sobre esos descriptores: un enlace en cualquier punto del
camino hace fallar la operación en lugar de seguirlo.
"""

import os
import secrets
import stat

from comun import ErrorSitio

_CARPETA = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _partes(relativa):
    partes = [p for p in str(relativa or "").split("/") if p not in ("", ".")]
    if not partes or any(p == ".." or "\x00" in p for p in partes) or len(relativa) > 300:
        raise ErrorSitio("ruta no válida")
    return partes


def abrir_carpeta(base, partes, crear_como=None):
    """Descriptor de la carpeta base/partes[0]/…; con crear_como=(uid, gid, modo) crea las que falten."""
    try:
        fd = os.open(base, _CARPETA)
    except OSError:
        raise ErrorSitio("la carpeta del sitio no está disponible")
    try:
        for parte in partes:
            try:
                siguiente = os.open(parte, _CARPETA, dir_fd=fd)
            except FileNotFoundError:
                if crear_como is None:
                    raise
                uid, gid, modo = crear_como
                os.mkdir(parte, modo, dir_fd=fd)
                os.chown(parte, uid, gid, dir_fd=fd, follow_symlinks=False)
                siguiente = os.open(parte, _CARPETA, dir_fd=fd)
            os.close(fd)
            fd = siguiente
        return fd
    except OSError:
        os.close(fd)
        raise ErrorSitio("solo se editan archivos dentro de la carpeta pública del sitio")


def leer(base, relativa, maximo):
    """(existe, bytes, stat) del archivo; None en bytes si supera el máximo. Nunca sigue enlaces."""
    *carpetas, nombre = _partes(relativa)
    try:
        dfd = abrir_carpeta(base, carpetas)
    except ErrorSitio:
        return False, b"", None
    try:
        try:
            fd = os.open(nombre, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=dfd)
        except FileNotFoundError:
            return False, b"", None
        except OSError:
            raise ErrorSitio("solo se editan archivos normales dentro de la carpeta pública del sitio")
        with os.fdopen(fd, "rb") as f:
            st = os.fstat(f.fileno())
            # Un enlace duro a un archivo de fuera también es «un archivo normal»: se rechaza.
            if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
                raise ErrorSitio("solo se editan archivos normales dentro de la carpeta pública del sitio")
            if st.st_size > maximo:
                return True, None, st
            return True, f.read(maximo + 1), st
    finally:
        os.close(dfd)


def escribir(base, relativa, contenido, uid, gid, modo, carpetas_como=None):
    """Reemplaza el archivo de forma atómica: temporal nuevo (O_EXCL), dueño y permisos por descriptor."""
    *carpetas, nombre = _partes(relativa)
    dfd = abrir_carpeta(base, carpetas, crear_como=carpetas_como)
    tmp = f".{nombre[:60]}.{secrets.token_hex(6)}.guardando"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dfd)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(contenido)
                os.fchown(f.fileno(), uid, gid)
                os.fchmod(f.fileno(), modo)
            os.replace(tmp, nombre, src_dir_fd=dfd, dst_dir_fd=dfd)
        except BaseException:
            try:
                os.unlink(tmp, dir_fd=dfd)
            except OSError:
                pass
            raise
    finally:
        os.close(dfd)
