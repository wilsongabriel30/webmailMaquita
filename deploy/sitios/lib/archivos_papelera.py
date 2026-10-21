"""Papelera del administrador de archivos: lo borrado desde el panel se puede recuperar durante 30 días.

Vive en la carpeta privada del sitio (tmp/papelera-archivos, fuera de la web) y la maneja el usuario del sitio
(estas funciones corren con él). Cada elemento es una carpeta <id>/ con lo borrado y un <id>.json con su ruta
original y la fecha. «maquita-sitios datos-noche» vacía lo que tenga más de DIAS días.
"""

import json
import os
import re
import shutil
import time

from archivos_rutas import nombre_valido, relativa, resolver
from comun import ErrorSitio

CARPETA = "papelera-archivos"
DIAS = 30
RE_ID = re.compile(r"^[0-9a-f]{12}$")


def ruta(meta):
    return os.path.join(meta["tmp"], CARPETA)


def _asegurar(papelera):
    if os.path.islink(papelera):
        raise ErrorSitio("la papelera del sitio no es una carpeta")
    os.makedirs(papelera, mode=0o700, exist_ok=True)


def borrar(raiz, papelera, rel):
    origen = resolver(raiz, rel, raiz_admitida=False)
    if not os.path.lexists(origen):
        raise ErrorSitio("no existe")
    _asegurar(papelera)
    ident = os.urandom(6).hex()
    os.mkdir(os.path.join(papelera, ident), 0o700)
    os.rename(origen, os.path.join(papelera, ident, os.path.basename(origen)))
    with open(os.path.join(papelera, ident + ".json"), "w") as f:
        json.dump({"ruta": relativa(raiz, origen), "fecha": time.strftime("%Y-%m-%d %H:%M"), "epoca": int(time.time())}, f)
    return {"id": ident, "ruta": relativa(raiz, origen)}


def _indice(papelera):
    if not os.path.isdir(papelera) or os.path.islink(papelera):
        return []
    salida = []
    for n in sorted(os.listdir(papelera)):
        if n.endswith(".json") and RE_ID.match(n[:-5]):
            try:
                with open(os.path.join(papelera, n)) as f:
                    datos = json.load(f)
                salida.append({"id": n[:-5], "ruta": str(datos["ruta"]), "fecha": datos.get("fecha"),
                               "epoca": int(datos.get("epoca") or 0)})
            except (OSError, ValueError, KeyError, TypeError):
                continue
    return sorted(salida, key=lambda e: -e["epoca"])


def listar(papelera):
    return {"elementos": [{k: e[k] for k in ("id", "ruta", "fecha")} for e in _indice(papelera)], "dias": DIAS}


def recuperar(raiz, papelera, ident):
    if not RE_ID.match(ident or ""):
        raise ErrorSitio("elemento no válido")
    entrada = next((e for e in _indice(papelera) if e["id"] == ident), None)
    if not entrada:
        raise ErrorSitio("ese elemento ya no está en la papelera")
    destino = resolver(raiz, entrada["ruta"], raiz_admitida=False)
    nombre_valido(os.path.basename(destino))
    if os.path.lexists(destino):
        raise ErrorSitio(f"ya existe «{entrada['ruta']}»: renómbrelo antes de recuperar")
    if not os.path.isdir(os.path.dirname(destino)):
        os.makedirs(os.path.dirname(destino), mode=0o750)
    contenido = os.path.join(papelera, ident)
    os.rename(os.path.join(contenido, os.listdir(contenido)[0]), destino)
    os.rmdir(contenido)
    os.remove(contenido + ".json")
    return {"ruta": entrada["ruta"]}


def _quitar(papelera, ident):
    carpeta = os.path.join(papelera, ident)
    if os.path.isdir(carpeta) and not os.path.islink(carpeta):
        shutil.rmtree(carpeta)  # rmtree no sigue enlaces simbólicos
    if os.path.lexists(carpeta + ".json"):
        os.remove(carpeta + ".json")


def vaciar(papelera, dias=None):
    """Sin `dias`: todo. Con `dias`: solo lo más antiguo (la limpieza de cada noche)."""
    limite = time.time() - dias * 86400 if dias is not None else None
    quitados = 0
    for e in _indice(papelera):
        if limite is None or e["epoca"] < limite:
            _quitar(papelera, e["id"])
            quitados += 1
    return {"vaciados": quitados}
