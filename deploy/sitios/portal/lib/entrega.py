"""Descargas hacia el portal: archivos del sitio, copias y el informe de visitas.

maquita-sitios deja cada descarga como <32 hex>.descarga en su carpeta subidas/ (de root, con el grupo del panel
general): el usuario del portal no puede leerla, y está bien que no pueda, porque ahí también están las del panel
general. El intermediario hace el traspaso:

  1. abre la descarga en subidas/ sin seguir enlaces (relativa a la carpeta ya abierta) y comprueba que es un
     archivo normal con un solo nombre;
  2. la hace del usuario del portal (fchown sobre el descriptor, 0600) y la pasa con rename a la carpeta del
     portal (subidas-portal, suya y 0700) con un nombre nuevo al azar; si las dos carpetas no comparten sistema
     de archivos, la copia desde ese mismo descriptor a un archivo nuevo (O_EXCL, sin seguir enlaces);
  3. devuelve solo ese nombre nuevo. El portal lo entrega con un enlace de un solo uso (lo reclama con un
     rename atómico, lo envía y lo borra) y borra lo que nadie pidió a tiempo.

Así el portal no lee nada fuera de su carpeta y lo único que recibe es lo que esta orden le dio.
"""

import errno
import os
import pwd
import re
import secrets
import stat

import rutas
from errores import ErrorPortal

RE_DESCARGA = re.compile(r"[0-9a-f]{32}\.descarga")
BLOQUE = 1024 * 1024


def _abrir_carpeta(ruta):
    try:
        return os.open(ruta, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise ErrorPortal(503, "Falta la carpeta de descargas del portal. Avise al administrador general.")


def _portal():
    try:
        pw = pwd.getpwnam(rutas.USUARIO_PORTAL)
    except KeyError:
        raise ErrorPortal(503, "El portal de dominio no está instalado en este servidor")
    return pw.pw_uid, pw.pw_gid


def _copiar(fd, destino_dir, nuevo, uid, gid):
    salida = os.open(nuevo, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=destino_dir)
    try:
        os.fchown(salida, uid, gid)
        os.lseek(fd, 0, os.SEEK_SET)
        while trozo := os.read(fd, BLOQUE):
            vista = memoryview(trozo)
            while vista:
                vista = vista[os.write(salida, vista):]
    except BaseException:
        os.close(salida)
        try:
            os.remove(nuevo, dir_fd=destino_dir)
        except OSError:
            pass
        raise
    os.close(salida)


def pasar(archivo):
    """Pasa la descarga `archivo` de subidas/ a la carpeta del portal. Devuelve (nombre nuevo, bytes)."""
    if not isinstance(archivo, str) or not RE_DESCARGA.fullmatch(archivo):
        raise ErrorPortal(503, "Respuesta no válida del ayudante de sitios")
    uid, gid = _portal()
    origen_dir = _abrir_carpeta(rutas.SUBIDAS)
    try:
        try:
            fd = os.open(archivo, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=origen_dir)
        except OSError:
            raise ErrorPortal(503, "No se encontró la descarga preparada")
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ErrorPortal(503, "Descarga no válida")
            destino_dir = _abrir_carpeta(rutas.SUBIDAS_PORTAL)
            nuevo = secrets.token_hex(16) + ".descarga"
            try:
                os.fchown(fd, uid, gid)
                os.fchmod(fd, 0o600)
                try:
                    os.rename(archivo, nuevo, src_dir_fd=origen_dir, dst_dir_fd=destino_dir)
                except OSError as e:
                    if e.errno != errno.EXDEV:
                        raise
                    _copiar(fd, destino_dir, nuevo, uid, gid)
            finally:
                os.close(destino_dir)
            return nuevo, info.st_size
        finally:
            os.close(fd)
    finally:
        # Lo que quede en subidas/ (copia entre sistemas de archivos o un fallo) no se deja ahí.
        try:
            os.remove(archivo, dir_fd=origen_dir)
        except OSError:
            pass
        os.close(origen_dir)


def entregar(datos, nombre):
    """Respuesta de maquita-sitios con {"archivo"} ⇒ la misma sin «archivo» y con {"descarga", "nombre", "bytes"}."""
    if not isinstance(datos, dict):
        raise ErrorPortal(503, "Respuesta no válida del ayudante de sitios")
    salida = dict(datos)
    nuevo, total = pasar(salida.pop("archivo", None))
    salida.update(descarga=nuevo, nombre=nombre, bytes=total)
    return salida
