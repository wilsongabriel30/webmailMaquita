"""Cuota de disco para las copias del sitio (v1.10): crear una copia y restaurar otra hacen crecer lo ocupado.

Las copias viven fuera de /srv/sitios (COPIAS/<sitio>/<id>.tar.gz) pero son del cliente, así que cuentan en el
espacio del dominio (cuotas.disco_mb ya las suma). Antes de crear o restaurar se estima cuánto va a crecer:

- copia nueva: lo que ocupó la última copia de ese sitio (el mejor indicio de lo que ocupará la siguiente) o,
  si todavía no tiene ninguna, lo que ocupan sus carpetas sin comprimir (por lo alto);
- restaurar: lo que ocupan sin comprimir las carpetas que trae la copia, menos lo que ocupan ahora las que
  sustituye, más la copia previa automática que se hace antes de tocar nada.
"""

import json
import os
import re
import tarfile

import cuotas
import rutas
from errores import ErrorPortal

RE_COPIA = re.compile(r"\d{8}-\d{6}")
PARTES = ("publico", "app")


def _meta(sitio):
    try:
        with open(os.path.join(rutas.META_SITIOS, f"{sitio}.json")) as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return {}
    return meta if isinstance(meta, dict) else {}


def _carpetas(sitio):
    """{parte: ruta} de las carpetas del sitio que entran en una copia (las mismas que copias_cliente._partes)."""
    meta = _meta(sitio)
    salida = {"publico": meta.get("publico") or os.path.join(rutas.RAIZ_SITIOS, sitio, "publico")}
    if meta.get("app_dir"):
        salida["app"] = meta["app_dir"]
    return {k: v for k, v in salida.items() if isinstance(v, str) and os.path.isdir(v)}


def _ultima(sitio):
    carpeta = os.path.join(rutas.COPIAS, sitio)
    try:
        nombres = sorted(n for n in os.listdir(carpeta) if n.endswith(".tar.gz") and RE_COPIA.fullmatch(n[:-7]))
    except OSError:
        return None
    return os.path.join(carpeta, nombres[-1]) if nombres else None


def estimar_copia(sitio):
    ultima = _ultima(sitio)
    if ultima:
        try:
            return os.lstat(ultima).st_size
        except OSError:
            pass
    return sum(cuotas._bytes_carpeta(r) for r in _carpetas(sitio).values())


def _sin_comprimir(archivo):
    """Bytes de los archivos de publico/ y app/ dentro de la copia (la crea root: es de fiar)."""
    total = 0
    try:
        with tarfile.open(archivo, "r:gz") as tar:
            for m in tar:
                if m.isfile() and m.name.split("/", 1)[0] in PARTES:
                    total += m.size
    except (OSError, tarfile.TarError):
        raise ErrorPortal(400, "No se pudo leer esa copia")
    return total


def comprobar_crear(ctx):
    cuotas.comprobar_disco(ctx.dominio, estimar_copia(ctx.sitio))


def comprobar_restaurar(ctx, ident):
    archivo = os.path.join(rutas.COPIAS, ctx.sitio, f"{ident}.tar.gz")
    if not os.path.isfile(archivo):
        raise ErrorPortal(404, "Esa copia no existe")
    traidas = _sin_comprimir(archivo)
    actuales = sum(cuotas._bytes_carpeta(r) for r in _carpetas(ctx.sitio).values())
    cuotas.comprobar_disco(ctx.dominio, traidas - actuales + estimar_copia(ctx.sitio))
