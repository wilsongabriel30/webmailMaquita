"""Configuración del cortafuegos: servicios con su origen permitido, IP de administración, puertos
adicionales y bloqueos manuales. Se guarda en /etc/maquita-cortafuegos/reglas.json (solo root).

Origen de cada servicio:
- «todos»: cualquiera en Internet.
- «admin»: solo las IP o redes de administración.
- «cerrado»: nadie (aunque el programa esté escuchando).
"""

import ipaddress
import json
import os
import re

DIR = "/etc/maquita-cortafuegos"
RUTA = os.path.join(DIR, "reglas.json")
ORIGENES = ("todos", "admin", "cerrado")

# Servicios conocidos del servidor, con su origen por defecto.
SERVICIOS = {
    "ssh": {"titulo": "Acceso remoto SSH / SFTP", "tcp": "22", "origen": "admin"},
    "panel": {"titulo": "Panel de administración", "tcp": "8443", "origen": "admin"},
    "correo-smtp": {"titulo": "Correo: recepción y envío (SMTP)", "tcp": "25,465,587", "origen": "todos"},
    "correo-lectura": {"titulo": "Correo: lectura en programas y móviles (IMAP/POP3)", "tcp": "143,993,110,995", "origen": "todos"},
    "sieve": {"titulo": "Filtros de correo desde programas (ManageSieve)", "tcp": "4190", "origen": "cerrado"},
    "web": {"titulo": "Web y webmail (HTTP/HTTPS)", "tcp": "80,443", "origen": "todos"},
    "dns": {"titulo": "DNS de los dominios propios", "tcp": "53", "udp": "53", "origen": "todos"},
    "ftp": {"titulo": "FTP seguro de los sitios web", "tcp": "21,40000:40100", "origen": "todos"},
}

RE_PUERTOS = re.compile(r"^\d{1,5}(?::\d{1,5})?(?:,\d{1,5}(?::\d{1,5})?){0,14}$")


class ErrorCortafuegos(Exception):
    pass


def red(valor):
    """IP o red (CIDR) válida, normalizada."""
    try:
        return str(ipaddress.ip_network(str(valor).strip(), strict=False))
    except ValueError:
        raise ErrorCortafuegos(f"IP o red no válida: {valor}")


def puertos(valor):
    v = str(valor).replace(" ", "").replace("-", ":")
    if not RE_PUERTOS.match(v):
        raise ErrorCortafuegos(f"puertos no válidos: {valor} (ej.: 8080 o 5000:5010 o 8080,8443)")
    for parte in v.split(","):
        extremos = [int(x) for x in parte.split(":")]
        if not all(1 <= x <= 65535 for x in extremos) or (len(extremos) == 2 and extremos[0] >= extremos[1]):
            raise ErrorCortafuegos(f"puertos fuera de rango: {parte}")
    return v


def por_defecto(admin=None):
    return {
        "servicios": {k: s["origen"] for k, s in SERVICIOS.items()},
        "admin": [red(a) for a in (admin or ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"])],
        "extras": [],
        "bloqueados": [],
    }


def validar(datos):
    """Comprueba y normaliza una configuración completa recibida del panel."""
    if not isinstance(datos, dict):
        raise ErrorCortafuegos("configuración no válida")
    servicios = {}
    for clave, origen in (datos.get("servicios") or {}).items():
        if clave not in SERVICIOS or origen not in ORIGENES:
            raise ErrorCortafuegos(f"servicio u origen no válido: {clave}={origen}")
        servicios[clave] = origen
    for clave, s in SERVICIOS.items():
        servicios.setdefault(clave, s["origen"])
    admin = sorted({red(a) for a in (datos.get("admin") or [])})
    if not admin and "admin" in servicios.values():
        raise ErrorCortafuegos("indique al menos una IP o red de administración")
    extras = []
    for e in datos.get("extras") or []:
        proto = e.get("protocolo", "tcp")
        origen = e.get("origen", "todos")
        desc = str(e.get("descripcion", "")).strip()[:80]
        if proto not in ("tcp", "udp") or origen not in ORIGENES[:2] or re.search(r"[\x00-\x1f\"\\]", desc):
            raise ErrorCortafuegos("puerto adicional no válido")
        extras.append({"puertos": puertos(e.get("puertos")), "protocolo": proto, "origen": origen, "descripcion": desc})
    if len(extras) > 50:
        raise ErrorCortafuegos("demasiados puertos adicionales (máximo 50)")
    bloqueados = []
    for b in datos.get("bloqueados") or []:
        motivo = str(b.get("motivo", "")).strip()[:80]
        if re.search(r"[\x00-\x1f\"\\]", motivo):
            raise ErrorCortafuegos("motivo no válido")
        bloqueados.append({"red": red(b.get("red")), "motivo": motivo})
    if len(bloqueados) > 1000:
        raise ErrorCortafuegos("demasiados bloqueos manuales (máximo 1000)")
    return {"servicios": servicios, "admin": admin, "extras": extras, "bloqueados": bloqueados}


def leer_ruta(ruta):
    with open(ruta) as f:
        return validar(json.load(f))


def leer():
    try:
        return leer_ruta(RUTA)
    except FileNotFoundError:
        return por_defecto()


def guardar(datos, ruta=RUTA):
    os.makedirs(DIR, mode=0o700, exist_ok=True)
    tmp = ruta + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    os.replace(tmp, ruta)
