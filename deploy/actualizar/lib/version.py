"""Versiones del servidor: la instalada, la disponible en el canal y su firma.

El código vive en un clon de git (/opt/maquita-webmail). El canal «estable» son las etiquetas vX.Y.Z del
repositorio, firmadas por el equipo (clave SSH): una etiqueta sin firma válida no se instala nunca, para
que nadie que consiga publicar en el repositorio pueda llegar por aquí a todos los servidores. Un canal
de rama (p. ej. «main») es solo para servidores de prueba.
"""

import json
import os
import re
import subprocess
import time

REPO = os.environ.get("MAQUITA_REPO", "/opt/maquita-webmail")
DIR_CONF = "/etc/maquita-actualizar"
DIR_ESTADO = "/var/lib/maquita-actualizar"
FIRMANTES = os.path.join(DIR_CONF, "firmantes")
CONFIG = os.path.join(DIR_CONF, "config.json")
DISPONIBLE = os.path.join(DIR_ESTADO, "disponible.json")
RE_VERSION = re.compile(r"^v(\d{1,4})\.(\d{1,4})\.(\d{1,4})$")
RE_RAMA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")


class ErrorActualizar(Exception):
    pass


def git(*args, tiempo=300):
    r = subprocess.run(["git", "-c", f"safe.directory={REPO}", "-C", REPO, *args],
                       capture_output=True, text=True, timeout=tiempo, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
                                                                            "GIT_TERMINAL_PROMPT": "0"})
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout).strip().splitlines()
        raise ErrorActualizar("git " + args[0] + ": " + (detalle[-1][:300] if detalle else f"código {r.returncode}"))
    return r.stdout.strip()


def leer_json(ruta, defecto):
    try:
        with open(ruta) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return defecto


def guardar_json(ruta, datos, modo=0o644):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, modo), "w") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    os.replace(tmp, ruta)


def config():
    conf = {"canal": "estable", "automatico": True}
    conf.update(leer_json(CONFIG, {}))
    return conf


def validar_config(datos):
    if not isinstance(datos, dict):
        raise ErrorActualizar("configuración no válida")
    canal = str(datos.get("canal", "estable")).strip()
    if canal != "estable" and (not RE_RAMA.match(canal) or ".." in canal):
        raise ErrorActualizar("canal no válido: «estable» o el nombre de una rama")
    return {"canal": canal, "automatico": bool(datos.get("automatico", True))}


def _clave(etiqueta):
    return tuple(int(x) for x in RE_VERSION.match(etiqueta).groups())


def actual():
    commit = git("rev-parse", "HEAD")
    try:
        version = git("describe", "--tags", "--match", "v*")
    except ErrorActualizar:
        version = commit[:7]
    cambios = git("status", "--porcelain", "--untracked-files=no")
    return {"commit": commit, "version": version, "cambios_locales": [l[3:] for l in cambios.splitlines()][:20]}


def firmada(etiqueta):
    """¿La etiqueta lleva una firma válida de alguien de la lista de firmantes?"""
    if not os.path.isfile(FIRMANTES) or not open(FIRMANTES).read().strip():
        return False
    r = subprocess.run(["git", "-c", f"safe.directory={REPO}", "-C", REPO, "-c", "gpg.format=ssh",
                        "-c", f"gpg.ssh.allowedSignersFile={FIRMANTES}", "verify-tag", etiqueta],
                       capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def buscar():
    """Trae del repositorio las etiquetas (y la rama del canal) y deja anotado lo disponible."""
    conf = config()
    git("fetch", "--quiet", "--tags", "--force", "--prune", "origin", tiempo=600)
    yo = actual()
    if conf["canal"] == "estable":
        etiquetas = sorted((e for e in git("tag", "-l", "v*").split() if RE_VERSION.match(e)), key=_clave)
        ref = etiquetas[-1] if etiquetas else None
        if ref:
            commit = git("rev-list", "-n", "1", ref)
            notas = git("tag", "-l", "--format=%(contents:body)", ref)[:3000]
            es_firmada = firmada(ref)
    else:
        git("fetch", "--quiet", "origin", f"+refs/heads/{conf['canal']}:refs/remotes/origin/{conf['canal']}", tiempo=600)
        ref = f"origin/{conf['canal']}"
        commit, notas, es_firmada = git("rev-parse", ref), "", None
    disponible = {"buscado": time.strftime("%Y-%m-%d %H:%M"), "canal": conf["canal"], "ref": ref, "nueva": False}
    if ref:
        nueva = commit != yo["commit"] and _avanza(yo["commit"], commit)
        cambios = git("log", "--no-merges", "--format=%s", f"{yo['commit']}..{commit}").splitlines() if nueva else []
        disponible.update(commit=commit, nueva=nueva, firmada=es_firmada, notas=notas, cambios=cambios[:60])
    guardar_json(DISPONIBLE, disponible)
    return disponible


def _avanza(desde, hasta):
    """Solo se actualiza hacia delante: la versión instalada tiene que estar contenida en la nueva."""
    r = subprocess.run(["git", "-c", f"safe.directory={REPO}", "-C", REPO, "merge-base", "--is-ancestor", desde, hasta],
                       capture_output=True, timeout=60)
    return r.returncode == 0


def objetivo(ref=None):
    """Qué se instalaría: la disponible del canal (comprobada) o una referencia concreta del canal."""
    disponible = leer_json(DISPONIBLE, {})
    if not disponible.get("nueva"):
        raise ErrorActualizar("no hay una versión nueva en el canal (pulse «Buscar»)")
    if ref and ref != disponible["ref"]:
        raise ErrorActualizar("solo se puede instalar la última versión disponible del canal")
    if disponible["canal"] == "estable" and not firmada(disponible["ref"]):
        raise ErrorActualizar(f"la versión {disponible['ref']} no tiene una firma válida del equipo: no se instala")
    return disponible
