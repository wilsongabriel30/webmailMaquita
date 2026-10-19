"""Descarga y verificación de paquetes oficiales (común a todas las aplicaciones del catálogo).

Regla: solo HTTPS, solo desde el origen oficial de cada proyecto y siempre comprobando una suma
publicada por el propio proyecto (o calculada por GitHub para el archivo que el proyecto adjunta a su
versión). Si la suma no coincide, la instalación se cancela.
"""

import hashlib
import json
import os
import re
import tarfile
import urllib.request
import zipfile

from comun import ErrorSitio

AGENTE = "instalador-sitios/1.0"


def descargar(url, destino, tope=400 * 1048576):
    if not url.startswith("https://"):
        raise ErrorSitio("descarga rechazada: solo HTTPS")
    pet = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pet, timeout=180) as r, open(destino, "wb") as f:
        leidos = 0
        while True:
            bloque = r.read(1 << 20)
            if not bloque:
                break
            leidos += len(bloque)
            if leidos > tope:
                raise ErrorSitio("descarga demasiado grande")
            f.write(bloque)


def texto(url, tope=2 * 1048576):
    pet = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "application/json"})
    with urllib.request.urlopen(pet, timeout=60) as r:
        return r.read(tope).decode("utf-8", "replace")


def suma(ruta, algoritmo="sha256"):
    h = hashlib.new(algoritmo)
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def comprobar(ruta, esperado, algoritmo, nombre):
    if not re.match(r"^[0-9a-f]{32,128}$", esperado or "") or suma(ruta, algoritmo) != esperado.lower():
        raise ErrorSitio(f"el paquete de {nombre} no coincide con su suma oficial: instalación cancelada")


def github_ultima(repo, patron):
    """(versión, url, sha256) del archivo de la última versión estable que cumple `patron`."""
    datos = json.loads(texto(f"https://api.github.com/repos/{repo}/releases/latest"))
    if datos.get("prerelease") or datos.get("draft"):
        raise ErrorSitio(f"la última versión publicada de {repo} no es estable")
    for a in datos.get("assets", []):
        if re.fullmatch(patron, a.get("name", "")):
            sha = (a.get("digest") or "").removeprefix("sha256:")
            if not re.fullmatch(r"[0-9a-f]{64}", sha):
                raise ErrorSitio(f"GitHub no publica la suma del paquete de {repo}")
            return datos.get("tag_name", "").lstrip("v"), a["browser_download_url"], sha
    raise ErrorSitio(f"no se encontró el paquete en la última versión de {repo}")


def _seguro(nombre):
    return not (nombre.startswith("/") or ".." in nombre.replace("\\", "/").split("/"))


def extraer(paquete, destino, quitar_prefijo=True):
    """Extrae .zip o .tar.gz rechazando rutas peligrosas. Si todo cuelga de una carpeta, la quita."""
    os.makedirs(destino, exist_ok=True)
    if zipfile.is_zipfile(paquete):
        with zipfile.ZipFile(paquete) as z:
            nombres = z.namelist()
            if not all(_seguro(n) for n in nombres):
                raise ErrorSitio("paquete con rutas no válidas")
            z.extractall(destino)
    else:
        with tarfile.open(paquete) as t:
            miembros = t.getmembers()
            for m in miembros:
                if not _seguro(m.name) or ((m.issym() or m.islnk()) and not _seguro(m.linkname)):
                    raise ErrorSitio("paquete con rutas no válidas")
            # filter="data": además rechaza dispositivos, permisos peligrosos y enlaces fuera del destino.
            t.extractall(destino, filter="data")
            nombres = [m.name for m in miembros]
    if quitar_prefijo:
        raices = {n.split("/")[0] for n in nombres if n.strip("/")}
        if len(raices) == 1:
            unica = os.path.join(destino, raices.pop())
            if os.path.isdir(unica):
                for n in os.listdir(unica):
                    os.replace(os.path.join(unica, n), os.path.join(destino, n))
                os.rmdir(unica)
