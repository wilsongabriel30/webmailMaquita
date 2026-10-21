"""Administrador de archivos del sitio: listar, subir, descargar, crear carpeta, mover, copiar y permisos.

Todas estas funciones corren ya con el usuario del sitio (como_usuario.py) y reciben la carpeta pública como
raíz; las rutas se resuelven con archivos_rutas.py. La papelera está en archivos_papelera.py y comprimir y
descomprimir en archivos_zip.py.
"""

import os
import shutil
import stat
import time

from archivos_rutas import dentro, nombre_valido, relativa, resolver, seguir
from comun import ErrorSitio

TOPE_LISTADO = 5000
TOPE_COPIA = 2 * 1024**3        # 2 GB por copia
TOPE_COPIA_ARCHIVOS = 50_000
TOPE_DESCARGA = 4 * 1024**3     # 4 GB
# Los que deja el panel: 644/755 (lectura pública), 600/700 (solo el dueño) y 640/750, los de serie del sitio
# (nginx lee por el grupo www-data).
MODOS = {"644": 0o644, "755": 0o755, "600": 0o600, "700": 0o700, "640": 0o640, "750": 0o750}


def _entrada(raiz, ruta, nombre):
    info = os.lstat(ruta)
    tipo = "carpeta" if stat.S_ISDIR(info.st_mode) else "archivo" if stat.S_ISREG(info.st_mode) else \
        "enlace" if stat.S_ISLNK(info.st_mode) else "otro"
    datos = {"nombre": nombre, "tipo": tipo, "bytes": info.st_size if tipo == "archivo" else None,
             "modificado": time.strftime("%Y-%m-%d %H:%M", time.localtime(info.st_mtime)),
             "permisos": oct(stat.S_IMODE(info.st_mode))[2:]}
    if tipo == "enlace":
        destino = os.path.realpath(ruta)
        datos["fuera"] = not dentro(os.path.realpath(raiz), destino)
        datos["apunta_a"] = None if datos["fuera"] else relativa(raiz, destino)
    return datos


def listar(raiz, rel):
    ruta = seguir(raiz, resolver(raiz, rel))
    if not os.path.isdir(ruta):
        raise ErrorSitio("esa carpeta no existe")
    nombres = sorted(os.listdir(ruta), key=lambda n: n.lower())
    entradas = []
    for nombre in nombres[:TOPE_LISTADO]:
        try:
            entradas.append(_entrada(raiz, os.path.join(ruta, nombre), nombre))
        except OSError:
            continue
    entradas.sort(key=lambda e: (e["tipo"] != "carpeta", e["nombre"].lower()))
    return {"ruta": relativa(raiz, ruta), "entradas": entradas, "recortado": len(nombres) > TOPE_LISTADO}


def _no_existe(ruta):
    if os.path.lexists(ruta):
        raise ErrorSitio(f"ya existe «{os.path.basename(ruta)}»")


def subir(raiz, rel, fd, reemplazar=False):
    """Copia lo que llega por `fd` (la subida que abrió root) a `rel`, sin seguir enlaces."""
    destino = resolver(raiz, rel, raiz_admitida=False)
    nombre_valido(os.path.basename(destino))
    if not os.path.isdir(os.path.dirname(destino)):
        raise ErrorSitio("la carpeta de destino no existe")
    if os.path.islink(destino) or os.path.isdir(destino):
        raise ErrorSitio("el destino es una carpeta o un enlace: elija otro nombre")
    if os.path.exists(destino) and not reemplazar:
        raise ErrorSitio(f"ya existe «{os.path.basename(destino)}» (marque «reemplazar» para sobrescribirlo)")
    tmp = os.path.join(os.path.dirname(destino), f".subiendo-{os.getpid()}-{os.urandom(4).hex()}")
    total = 0
    try:
        with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640), "wb") as f:
            os.lseek(fd, 0, os.SEEK_SET)
            while bloque := os.read(fd, 1 << 20):
                total += len(bloque)
                f.write(bloque)
        os.replace(tmp, destino)
    finally:
        if os.path.lexists(tmp):
            os.remove(tmp)
    return {"ruta": relativa(raiz, destino), "bytes": total}


def descargar(raiz, rel, fd):
    """Escribe el archivo en `fd` (abierto por root en subidas/ para que el panel lo entregue)."""
    ruta = resolver(raiz, rel, raiz_admitida=False)
    if os.path.islink(ruta):
        ruta = seguir(raiz, ruta)
    if not os.path.isfile(ruta):
        raise ErrorSitio("solo se descargan archivos (para una carpeta, comprímala primero)")
    if os.path.getsize(ruta) > TOPE_DESCARGA:
        raise ErrorSitio("el archivo supera 4 GB: descárguelo por SFTP")
    total = 0
    with open(os.open(ruta, os.O_RDONLY | os.O_NOFOLLOW), "rb") as f:
        while bloque := f.read(1 << 20):
            total += len(bloque)
            _escribir_todo(fd, bloque)
    return {"nombre": os.path.basename(ruta), "bytes": total}


def _escribir_todo(fd, datos):
    vista = memoryview(datos)
    while vista:
        vista = vista[os.write(fd, vista):]


def carpeta(raiz, rel):
    ruta = resolver(raiz, rel, raiz_admitida=False)
    nombre_valido(os.path.basename(ruta))
    _no_existe(ruta)
    os.mkdir(ruta, 0o750)
    return {"ruta": relativa(raiz, ruta)}


def _medir(ruta):
    """Tamaño y número de elementos, sin seguir enlaces."""
    if not os.path.isdir(ruta) or os.path.islink(ruta):
        return os.lstat(ruta).st_size, 1
    total, cuantos = 0, 0
    for actual, dirs, archivos in os.walk(ruta):
        for n in dirs + archivos:
            cuantos += 1
            try:
                total += os.lstat(os.path.join(actual, n)).st_size
            except OSError:
                pass
        if cuantos > TOPE_COPIA_ARCHIVOS:
            break
    return total, cuantos


def _par(raiz, origen, destino):
    o = resolver(raiz, origen, raiz_admitida=False)
    d = resolver(raiz, destino, raiz_admitida=False)
    nombre_valido(os.path.basename(d))
    if not os.path.lexists(o):
        raise ErrorSitio("el origen no existe")
    _no_existe(d)
    if not os.path.isdir(os.path.dirname(d)):
        raise ErrorSitio("la carpeta de destino no existe")
    if os.path.isdir(o) and not os.path.islink(o) and dentro(o, d):
        raise ErrorSitio("no se puede mover ni copiar una carpeta dentro de sí misma")
    return o, d


def mover(raiz, origen, destino):
    """Renombrar o mover (dentro de la carpeta del sitio). Un enlace se mueve como enlace."""
    o, d = _par(raiz, origen, destino)
    os.rename(o, d)
    return {"ruta": relativa(raiz, d)}


def copiar(raiz, origen, destino):
    o, d = _par(raiz, origen, destino)
    tamano, cuantos = _medir(o)
    if tamano > TOPE_COPIA or cuantos > TOPE_COPIA_ARCHIVOS:
        raise ErrorSitio("demasiado grande para copiar desde el panel (máximo 2 GB y 50 000 elementos)")
    if os.path.islink(o):
        os.symlink(os.readlink(o), d)
    elif os.path.isdir(o):
        shutil.copytree(o, d, symlinks=True)  # los enlaces se copian como enlaces, no se siguen
    else:
        shutil.copy2(o, d, follow_symlinks=False)
    return {"ruta": relativa(raiz, d)}


def permisos(raiz, rel, modo):
    if modo not in MODOS:
        raise ErrorSitio("permisos no admitidos (644, 755, 600, 700, 640 o 750)")
    ruta = resolver(raiz, rel, raiz_admitida=False)
    if os.path.islink(ruta) or not os.path.exists(ruta):
        raise ErrorSitio("no existe o es un enlace simbólico (los enlaces no tienen permisos propios)")
    os.chmod(ruta, MODOS[modo])  # ya comprobado que no es un enlace; corre con el usuario del sitio
    return {"ruta": relativa(raiz, ruta), "permisos": modo}
