# -*- coding: utf-8 -*-
"""
Propietario uniforme en el NFS del almacén.
El Drive de FARO corre como `sistemas` (uid 1000, grupo www-data 33) y este servicio (y el sincronizador del correo)
corren como root: lo que se creaba como root:root luego no se podía mover a la papelera/retención desde FARO
(«No se pudo vaciar la papelera»). Al instalar este módulo, toda carpeta/archivo que cree `nucleo_archivos`
queda como ALMACEN_UID:ALMACEN_GID (por defecto 1000:33). Sin efecto si no se corre como root.
"""
import os
import shutil

UID = int(os.getenv('ALMACEN_UID', '1000'))
GID = int(os.getenv('ALMACEN_GID', '33'))


def fijar(ruta):
    try:
        if os.geteuid() == 0 and os.path.lexists(ruta):
            os.chown(ruta, UID, GID, follow_symlinks=False)
    except OSError:
        pass


def _envolver(funcion, indices):
    def envuelta(*args, **kwargs):
        r = funcion(*args, **kwargs)
        for i in indices:
            if i < len(args):
                fijar(args[i])
        return r
    return envuelta


def _makedirs(ruta, *args, **kwargs):
    # crea y fija también los padres nuevos
    faltantes = []
    p = os.path.abspath(ruta)
    while p and not os.path.isdir(p):
        faltantes.append(p)
        p = os.path.dirname(p)
    os.makedirs(ruta, *args, **kwargs)
    for f in faltantes:
        fijar(f)


class _OsProxy:
    def __init__(self, base):
        self._base = base
        self.makedirs = _makedirs
        self.replace = _envolver(base.replace, [1])
        self.rename = _envolver(base.rename, [1])
        self.link = _envolver(base.link, [1])

    def __getattr__(self, nombre):
        return getattr(self._base, nombre)


class _ShutilProxy:
    def __init__(self, base):
        self._base = base
        self.copy2 = _envolver(base.copy2, [1])
        self.copytree = _envolver(base.copytree, [1])
        self.move = _envolver(base.move, [1])

    def __getattr__(self, nombre):
        return getattr(self._base, nombre)


def instalar(modulo_nucleo):
    """Sustituye `os` y `shutil` dentro del módulo nucleo_archivos por versiones que fijan el propietario."""
    if os.geteuid() != 0:
        return
    if not isinstance(modulo_nucleo.os, _OsProxy):
        modulo_nucleo.os = _OsProxy(modulo_nucleo.os)
    if hasattr(modulo_nucleo, 'shutil') and not isinstance(modulo_nucleo.shutil, _ShutilProxy):
        modulo_nucleo.shutil = _ShutilProxy(modulo_nucleo.shutil)
