"""Comprimir en .zip y descomprimir .zip, .tar.gz, .tgz y .tar desde el administrador de archivos.

Corre con el usuario del sitio. Al descomprimir se rechaza el archivo entero, antes de escribir nada, si trae
rutas absolutas o con «..» («zip slip»), enlaces simbólicos o duros, dispositivos, más de TOPE_ARCHIVOS
elementos o más de TOPE_BYTES descomprimido; y mientras se escribe se cuentan los bytes reales, porque el
tamaño que declara un .zip puede ser falso (bombas). Cada archivo se escribe sin seguir enlaces (O_NOFOLLOW)
en una carpeta resuelta dentro del sitio.
"""

import os
import stat
import tarfile
import zipfile
import zlib

from archivos_rutas import dentro, nombre_valido, partes, relativa, resolver, seguir
from comun import ErrorSitio

TOPE_BYTES = 1024**3        # 1 GB descomprimido
TOPE_ARCHIVOS = 20_000
TOPE_COMPRIMIR = 2 * 1024**3
EXTENSIONES = (".zip", ".tar.gz", ".tgz", ".tar")


class _Bomba(ErrorSitio):
    pass


# --- Comprimir ---


def comprimir(raiz, rutas, destino):
    """Crea `destino` (.zip) con las rutas indicadas. Los enlaces simbólicos no se incluyen."""
    if not isinstance(rutas, list) or not 1 <= len(rutas) <= 500:
        raise ErrorSitio("elija entre 1 y 500 elementos")
    final = resolver(raiz, destino, raiz_admitida=False)
    nombre_valido(os.path.basename(final))
    if not final.lower().endswith(".zip"):
        raise ErrorSitio("el archivo comprimido debe terminar en .zip")
    if os.path.lexists(final):
        raise ErrorSitio(f"ya existe «{os.path.basename(final)}»")
    origenes = [resolver(raiz, r, raiz_admitida=True) for r in rutas]
    total, cuantos = 0, 0
    tmp = final + f".{os.urandom(4).hex()}.parcial"
    try:
        with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640), "wb") as f, \
                zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for origen in origenes:
                base = os.path.dirname(origen)
                for ruta in _recorrer(origen):
                    if ruta in (tmp, final):
                        continue
                    info = os.lstat(ruta)
                    cuantos += 1
                    total += info.st_size if stat.S_ISREG(info.st_mode) else 0
                    if total > TOPE_COMPRIMIR or cuantos > TOPE_ARCHIVOS * 5:
                        raise ErrorSitio("demasiado para comprimir desde el panel (máximo 2 GB y 100 000 elementos)")
                    z.write(ruta, os.path.relpath(ruta, base))
        os.replace(tmp, final)
    finally:
        if os.path.lexists(tmp):
            os.remove(tmp)
    return {"ruta": relativa(raiz, final), "elementos": cuantos}


def _recorrer(origen):
    """Archivos y carpetas, sin enlaces (zipfile seguiría el enlace y metería lo que apunta)."""
    if os.path.islink(origen) or not os.path.lexists(origen):
        return
    yield origen
    if os.path.isdir(origen):
        for actual, dirs, archivos in os.walk(origen):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(actual, d))]
            for n in sorted(dirs) + sorted(archivos):
                ruta = os.path.join(actual, n)
                info = os.lstat(ruta)
                if stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode):
                    yield ruta


# --- Descomprimir ---


def _nombre_miembro(nombre):
    """Ruta de un miembro del archivo → lista de partes; rechaza las peligrosas («zip slip»)."""
    if not nombre or nombre.startswith("/") or "\\" in nombre or (len(nombre) > 1 and nombre[1] == ":"):
        raise ErrorSitio(f"el archivo trae una ruta no válida: {nombre[:100]}")
    try:
        trozos = partes(nombre.rstrip("/") or ".")
    except ErrorSitio:
        raise ErrorSitio(f"el archivo trae una ruta no válida: {nombre[:100]}")
    return trozos


def _miembros_zip(z):
    salida, total = [], 0
    for i in z.infolist():
        tipo = (i.external_attr >> 16) & 0o170000
        if tipo and tipo not in (stat.S_IFREG, stat.S_IFDIR):
            raise ErrorSitio(f"el archivo trae un enlace o un archivo especial: {i.filename[:100]}")
        total += i.file_size
        salida.append((_nombre_miembro(i.filename), i.is_dir(), i.file_size, i))
    return salida, total


def _miembros_tar(t):
    salida, total = [], 0
    for m in t:
        if not (m.isfile() or m.isdir()):
            raise ErrorSitio(f"el archivo trae un enlace o un archivo especial: {m.name[:100]}")
        total += m.size
        salida.append((_nombre_miembro(m.name), m.isdir(), m.size, m))
        # Se corta en cuanto se pasa: leer el resto de un .tar.gz obliga a descomprimirlo entero.
        _comprobar(salida, total)
    return salida, total


def _carpeta_segura(raiz, destino, trozos):
    """Crea (si hace falta) cada carpeta del camino comprobando que ninguna sea un enlace que salga."""
    actual = destino
    for p in trozos:
        actual = os.path.join(actual, p)
        if os.path.islink(actual) or (os.path.lexists(actual) and not os.path.isdir(actual)):
            raise ErrorSitio(f"«{relativa(raiz, actual)}» ya existe y no es una carpeta")
        if not os.path.exists(actual):
            os.mkdir(actual, 0o750)
    if not dentro(os.path.realpath(raiz), os.path.realpath(actual)):
        raise ErrorSitio("ruta no válida: un enlace simbólico sale de la carpeta del sitio")
    return actual


def descomprimir(raiz, archivo, destino):
    origen = resolver(raiz, archivo, raiz_admitida=False)
    if os.path.islink(origen):
        origen = seguir(raiz, origen)
    if not os.path.isfile(origen):
        raise ErrorSitio("el archivo comprimido no existe")
    carpeta = seguir(raiz, resolver(raiz, destino))
    if not os.path.isdir(carpeta):
        raise ErrorSitio("la carpeta de destino no existe")
    if zipfile.is_zipfile(origen):
        with zipfile.ZipFile(origen) as z:
            miembros, total = _miembros_zip(z)
            _comprobar(miembros, total)
            escritos = _extraer(raiz, carpeta, miembros, lambda i: z.open(i))
    else:
        try:
            with tarfile.open(origen, "r:*") as t:
                miembros, total = _miembros_tar(t)
                _comprobar(miembros, total)
                escritos = _extraer(raiz, carpeta, miembros, lambda m: t.extractfile(m))
        except tarfile.TarError:
            raise ErrorSitio("no es un .zip ni un .tar.gz válido")
    return {"ruta": relativa(raiz, carpeta), "archivos": escritos}


def _comprobar(miembros, total):
    if len(miembros) > TOPE_ARCHIVOS:
        raise _Bomba(f"el archivo tiene más de {TOPE_ARCHIVOS} elementos")
    if total > TOPE_BYTES:
        raise _Bomba("descomprimido ocuparía más de 1 GB: súbalo por SFTP o descomprímalo por partes")


def _extraer(raiz, carpeta, miembros, abrir):
    escritos, total = 0, 0
    for trozos, es_carpeta, declarado, ref in miembros:
        if not trozos:
            continue
        if es_carpeta:
            _carpeta_segura(raiz, carpeta, trozos)
            continue
        padre = _carpeta_segura(raiz, carpeta, trozos[:-1])
        ruta = os.path.join(padre, trozos[-1])
        if os.path.islink(ruta) or os.path.isdir(ruta):
            raise ErrorSitio(f"«{relativa(raiz, ruta)}» ya existe y es una carpeta o un enlace")
        leido = 0
        fuente = abrir(ref)
        try:
            with fuente, open(os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o640), "wb") as f:
                while bloque := fuente.read(1 << 20):
                    leido += len(bloque)
                    total += len(bloque)
                    if leido > declarado or total > TOPE_BYTES:
                        raise _Bomba("el archivo se infla más de lo que declara (posible bomba de descompresión)")
                    f.write(bloque)
        except _Bomba:
            os.remove(ruta)
            raise
        except (zipfile.BadZipFile, tarfile.TarError, zlib.error, EOFError):
            # zipfile no da más bytes de los declarados, pero un archivo manipulado falla en su CRC al final.
            os.remove(ruta)
            raise ErrorSitio(f"el archivo comprimido está dañado (en «{'/'.join(trozos)[:100]}»)")
        escritos += 1
    return escritos
