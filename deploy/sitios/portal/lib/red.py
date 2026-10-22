"""¿El servidor de un repositorio está en Internet? Desde el portal, un repositorio nunca puede apuntar a la red
interna del servidor (127.0.0.1, la red de la oficina, los otros servicios): sería una puerta hacia dentro.

Lo mismo comprueba maquita-sitios para el git de los sitios PHP (deploy/sitios/lib/red_publica.py); aquí se usa
para las aplicaciones propias, cuyo git desde el panel general no se limita (lo maneja el superadministrador).
"""

import ipaddress
import re
import socket

from errores import ErrorPortal

RE_HOST_HTTPS = re.compile(r"https://([A-Za-z0-9](?:[A-Za-z0-9.-]{0,252}))(?::\d{1,5})?/.*")


def es_publica(direccion):
    """Las pruebas la sustituyen: las direcciones de documentación (192.0.2.x…) no son públicas."""
    return direccion.is_global


def host_publico(host):
    try:
        direcciones = [ipaddress.ip_address(host.strip("[]"))]
    except ValueError:
        try:
            direcciones = [ipaddress.ip_address(d[4][0].split("%", 1)[0])
                           for d in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)]
        except (socket.gaierror, UnicodeError):
            raise ErrorPortal(400, f"No se encontró el servidor de git {host}")
    if not direcciones or not all(es_publica(d) for d in direcciones):
        raise ErrorPortal(400, f"El servidor de git {host} no está en Internet (dirección privada o local): no se admite")
    return host


def repositorio_https(url):
    """Un repositorio público por https:// cuyo servidor está en Internet, o 400."""
    m = RE_HOST_HTTPS.fullmatch(url) if isinstance(url, str) else None
    if not m or ".." in url or "@" in url:
        raise ErrorPortal(400, "Repositorio no válido: use la dirección https:// de un repositorio público "
                               "(sin usuario ni clave)")
    host_publico(m.group(1))
    return url
