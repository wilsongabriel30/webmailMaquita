"""Utilidades comunes del ayudante de sitios web: rutas, metadatos, órdenes y claves."""

import base64
import glob
import json
import os
import re
import secrets
import string
import subprocess

RAIZ_SITIOS = "/srv/sitios"
META_DIR = "/etc/maquita-sitios"
PAPELERA = "/srv/sitios-papelera"
NGINX_DISP = "/etc/nginx/sites-available"
NGINX_ACT = "/etc/nginx/sites-enabled"
ACME_WEBROOT = "/var/www/certbot"
GRUPO_SITIOS = "sitios"
LISTA_FTP = "/etc/vsftpd.sitios"
WP_CLI = "/usr/local/bin/wp"
PREFIJO_CONF = "sitio-"


class ErrorSitio(Exception):
    """Error que se devuelve al panel como {"error": ...}."""


def ejecutar(cmd, entrada=None, como=None, cwd=None, tiempo=600, env_extra=None):
    """Ejecuta una orden sin shell. Devuelve stdout; si falla, ErrorSitio con el final de stderr."""
    nombre = os.path.basename(cmd[0])
    if como:
        cmd = ["runuser", "-u", como, "--"] + list(cmd)
    env = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"}
    if env_extra:
        env.update(env_extra)
    if como:
        env["HOME"] = "/tmp"
    r = subprocess.run(
        cmd, input=entrada, capture_output=True, text=True, cwd=cwd, timeout=tiempo, env=env
    )
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout or "").strip().splitlines()
        raise ErrorSitio(f"{nombre}: " + (detalle[-1][:300] if detalle else f"código {r.returncode}"))
    return r.stdout


def volcar(cmd, destino, tiempo=1800):
    """Copia de una base de datos directa al archivo (0600), en binario: hay aplicaciones (Matomo)
    que guardan datos que no son texto UTF-8."""
    with open(os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=tiempo, cwd="/tmp",
                           env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"})
    if r.returncode != 0:
        detalle = r.stderr.decode(errors="replace").strip().splitlines()
        raise ErrorSitio("no se pudo copiar la base antes de borrarla" + (f": {detalle[-1][:200]}" if detalle else ""))


def clave(n=20):
    """Contraseña aleatoria con letras, números y un símbolo seguro para shells y URL."""
    alfabeto = string.ascii_letters + string.digits
    base = "".join(secrets.choice(alfabeto) for _ in range(n))
    return base + secrets.choice("#%+=") + secrets.choice(string.digits)


def slug(dominio):
    """Identificador corto y estable para usuario de sistema, base de datos y pool de PHP."""
    limpio = re.sub(r"[^a-z0-9]", "", dominio.split(".")[0])[:12] or "sitio"
    return f"{limpio}{hash_estable(dominio) % 10000:04d}"


def hash_estable(texto):
    """Hash determinista (hash() de Python cambia entre ejecuciones)."""
    import hashlib

    return int(hashlib.sha256(texto.encode()).hexdigest()[:12], 16)


def ruta_meta(dominio):
    return os.path.join(META_DIR, f"{dominio}.json")


def leer_meta(dominio):
    try:
        with open(ruta_meta(dominio)) as f:
            return json.load(f)
    except FileNotFoundError:
        raise ErrorSitio(f"el sitio {dominio} no existe")


def guardar_meta(meta):
    os.makedirs(META_DIR, mode=0o700, exist_ok=True)
    ruta = ruta_meta(meta["dominio"])
    tmp = ruta + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    os.replace(tmp, ruta)


def todos_los_meta():
    salida = []
    for p in sorted(glob.glob(os.path.join(META_DIR, "*.json"))):
        with open(p) as f:
            salida.append(json.load(f))
    return salida


def version_php():
    """Versión de PHP-FPM instalada (p. ej. «8.4») o None."""
    versiones = sorted(
        (os.path.basename(os.path.dirname(os.path.dirname(p))) for p in glob.glob("/etc/php/*/fpm/pool.d")),
        key=lambda v: [int(x) for x in v.split(".")],
    )
    return versiones[-1] if versiones else None


def de_base64(texto):
    """Decodifica base64url (los textos libres llegan así para no pasar espacios por sudo)."""
    relleno = "=" * (-len(texto) % 4)
    return base64.urlsafe_b64decode(texto + relleno).decode("utf-8")
