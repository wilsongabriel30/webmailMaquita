"""Bloqueo de IP por sitio: direcciones o redes (IPv4 e IPv6) que reciben 403 en este sitio y solo en este.

El bloqueo de todo el servidor (cortafuegos, fail2ban, países) sigue en Seguridad; esto es para cortar a quien
abusa de un sitio concreto (un formulario, un robot que copia contenido) sin tocar el correo ni los demás sitios.
Cada valor pasa por `ipaddress` y se escribe en su forma normalizada («deny 192.0.2.0/24;»).
"""

import ipaddress
import re

import web_comun as w
from comun import ErrorSitio

MAXIMO = 500
RE_IP = re.compile(r"^[0-9A-Fa-f:.]{2,45}(?:/\d{1,3})?$")  # antes de ipaddress: ni espacios ni saltos de línea


def validar(meta, datos):
    redes = []
    for valor in w.lista(datos, MAXIMO, "IP bloqueadas"):
        if not isinstance(valor, str) or not RE_IP.fullmatch(valor):
            raise ErrorSitio(f"IP o red no válida: {str(valor)[:50]}")
        try:
            red = ipaddress.ip_network(valor, strict=False)
        except ValueError:
            raise ErrorSitio(f"IP o red no válida: {valor[:50]}")
        if red.prefixlen == 0:
            raise ErrorSitio("no se puede bloquear Internet entero (/0)")
        texto = str(red.network_address) if red.prefixlen == red.max_prefixlen else str(red)
        if texto not in redes:
            redes.append(texto)
    return redes


def fragmentos(meta, ajustes):
    if not ajustes:
        return {}
    # Se vuelve a normalizar al generar: un meta editado a mano tampoco puede colar texto en nginx.
    lineas = ["# IP bloqueadas en este sitio"]
    lineas += [f"deny {r};" for r in validar(meta, ajustes)]
    return {"servidor": "\n".join(lineas)}


def estado(meta, ajustes):
    return {"lista": ajustes or [], "maximo": MAXIMO}
