"""¿Un servidor de git está en Internet? Para que un despliegue no sirva de puente hacia la red interna.

El repositorio lo elige quien administra el sitio (también un cliente del portal): sin esta comprobación podría
hacer que el servidor se conecte a 127.0.0.1, a la red de la oficina o a la de los otros servicios. Se admiten
solo nombres cuyas direcciones son TODAS públicas (ipaddress.is_global) y direcciones públicas escritas tal cual.
"""

import ipaddress
import socket

from comun import ErrorSitio


def es_publica(direccion):
    """Las pruebas la sustituyen: las direcciones de documentación (192.0.2.x…) no son públicas."""
    return direccion.is_global


def comprobar(host):
    """Devuelve el nombre si todas sus direcciones son públicas; si no, ErrorSitio."""
    if not isinstance(host, str) or not host:
        raise ErrorSitio("servidor de git no válido")
    limpio = host.strip("[]")
    try:
        direcciones = [ipaddress.ip_address(limpio)]
    except ValueError:
        try:
            datos = socket.getaddrinfo(limpio, None, proto=socket.IPPROTO_TCP)
        except (socket.gaierror, UnicodeError):
            raise ErrorSitio(f"no se encontró el servidor de git {host}")
        direcciones = [ipaddress.ip_address(d[4][0].split("%", 1)[0]) for d in datos]
    if not direcciones or not all(es_publica(d) for d in direcciones):
        raise ErrorSitio(f"el servidor de git {host} no está en Internet (dirección privada o local): no se admite")
    return host
