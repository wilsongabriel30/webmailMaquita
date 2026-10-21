"""Alcance de cada petición: qué sitio es, de qué dominio asignado cuelga y si su nombre está reservado.

- El sitio es un dominio asignado D o un subdominio suyo (x.D). Si no, «No encontrado» (404): no se
  confirma que exista lo ajeno.
- Dentro del alcance, los nombres del correo y del servidor están reservados (403): no se pueden crear
  ni tocar como sitio aunque cuelguen de un dominio propio.
"""

import glob
import json
import os
import re

import rutas
from errores import ErrorPortal, no_encontrado

RE_DOMINIO = re.compile(r"^(?=.{4,200}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
# Para el alcance se admite también «_» (_dmarc.<dominio>): así un nombre propio con «_» responde
# «reservado» (403) y no «no encontrado».
RE_NOMBRE = re.compile(r"^(?=.{4,200}$)([a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
PREFIJOS_RESERVADOS = ("mail.", "imap.", "smtp.", "pop3.", "autoconfig.", "autodiscover.", "mta-sts.",
                       "webmail.", "correo.")


def nombre_valido(valor):
    """El nombre tal cual llega (minúsculas, sin «www.»), o 404 si ni siquiera es un nombre."""
    if not isinstance(valor, str):
        raise no_encontrado()
    valor = valor.strip().lower()
    if valor.startswith("www."):
        valor = valor[4:]
    if not RE_NOMBRE.fullmatch(valor):
        raise no_encontrado()
    return valor


def dominio_asignado(sitio, dominios):
    """El dominio asignado del que cuelga `sitio` (el más largo, si hay varios), o 404."""
    candidatos = [d for d in dominios if sitio == d or sitio.endswith("." + d)]
    if not candidatos:
        raise no_encontrado()
    return max(candidatos, key=len)


def en_alcance(sitio, dominio):
    return sitio == dominio or sitio.endswith("." + dominio)


def mail_host():
    """MAIL_HOST del correo (backend/.env), el nombre por el que se entra al correo y al panel."""
    try:
        with open(rutas.ENTORNO_CORREO) as f:
            for linea in f:
                if linea.startswith("MAIL_HOST="):
                    return linea.split("=", 1)[1].strip().strip("'\"").lower() or None
    except OSError:
        pass
    return None


def nombres_de_nginx():
    """server_name de los vhosts activos que NO son sitios de maquita-sitios (correo, panel, portal...)."""
    usados = set()
    for ruta in glob.glob(os.path.join(rutas.NGINX_ACTIVOS, "*")):
        if os.path.basename(ruta).startswith(rutas.PREFIJO_VHOST):
            continue
        try:
            with open(ruta, errors="replace") as f:
                for linea in f:
                    linea = linea.strip()
                    if linea.startswith("server_name"):
                        usados.update(n.lower() for n in linea.split("#", 1)[0].rstrip("; ").split()[1:])
        except OSError:
            continue
    return usados


def comprobar_reservado(sitio, portales):
    """403 si `sitio` es un nombre que el portal nunca puede crear ni tocar."""
    motivo = None
    if sitio.startswith(PREFIJOS_RESERVADOS) or any(p.startswith("_") for p in sitio.split(".")):
        motivo = "es del correo"
    elif sitio == mail_host() or sitio in portales:
        motivo = "es el nombre del servidor de correo"
    else:
        nginx = nombres_de_nginx()
        if sitio in nginx or f"www.{sitio}" in nginx:
            motivo = "lo usa otro servicio de este servidor"
    if motivo:
        raise ErrorPortal(403, f"{sitio} está reservado: {motivo}")


def sitio_existe(sitio):
    return os.path.isfile(os.path.join(rutas.META_SITIOS, f"{sitio}.json"))


def es_alias(sitio):
    """¿Lo muestra ya otro sitio como alias? (El nombre de ese otro sitio no se dice: puede ser ajeno)."""
    for ruta in glob.glob(os.path.join(rutas.META_SITIOS, "*.json")):
        try:
            with open(ruta) as f:
                if sitio in (json.load(f).get("alias") or []):
                    return True
        except (OSError, ValueError):
            continue
    return False


def sitios_de(dominio):
    """Sitios (por sus metadatos) que cuelgan de un dominio asignado."""
    salida = []
    for ruta in sorted(glob.glob(os.path.join(rutas.META_SITIOS, "*.json"))):
        nombre = os.path.basename(ruta)[:-5]
        if RE_DOMINIO.fullmatch(nombre) and en_alcance(nombre, dominio):
            salida.append(nombre)
    return salida
