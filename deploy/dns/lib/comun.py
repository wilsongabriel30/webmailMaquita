"""Rutas, errores y utilidades del ayudante de DNS (maquita-dns)."""

import base64
import json
import os
import subprocess

DATOS = "/etc/maquita-dns"  # una zona por archivo JSON + servidor.json (solo root)
ZONAS_BIND = "/etc/bind/zonas"
LISTA_BIND = "/etc/bind/maquita-zonas.conf"  # incluido desde named.conf.local
SERVIDOR = os.path.join(DATOS, "servidor.json")
DKIM_DIR = "/var/lib/rspamd/dkim"
SELECTOR_DKIM = "mail"


class ErrorDns(Exception):
    """Error que se devuelve al panel como {"error": ...}."""


def ejecutar(cmd, entrada=None, tiempo=120):
    env = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"}
    r = subprocess.run(cmd, input=entrada, capture_output=True, text=True, timeout=tiempo, env=env)
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout or "").strip().splitlines()
        raise ErrorDns(f"{os.path.basename(cmd[0])}: " + (detalle[-1][:300] if detalle else f"código {r.returncode}"))
    return r.stdout


def leer_json(ruta, defecto=None):
    try:
        with open(ruta) as f:
            return json.load(f)
    except FileNotFoundError:
        if defecto is not None:
            return defecto
        raise


def guardar_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta), mode=0o700, exist_ok=True)
    tmp = ruta + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    os.replace(tmp, ruta)


def escribir(ruta, texto, modo=0o644, grupo=None):
    tmp = ruta + ".tmp"
    with open(tmp, "w") as f:
        f.write(texto)
    os.chmod(tmp, modo)
    if grupo is not None:
        os.chown(tmp, 0, grupo)
    os.replace(tmp, ruta)


def de_base64(texto):
    """Los valores libres llegan en base64url (espacios, comillas y punto y coma no pasan por sudo)."""
    try:
        return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4)).decode("utf-8")
    except Exception:
        raise ErrorDns("valor mal codificado")


def servidor():
    """IP pública del correo y de la web, servidores de nombres propios y correo del responsable."""
    datos = leer_json(SERVIDOR, {})
    if not datos.get("ip_correo") or not datos.get("ns"):
        raise ErrorDns("faltan los datos del servidor (IP pública y servidores de nombres): complételos en «Zonas DNS → Ajustes»")
    return datos
