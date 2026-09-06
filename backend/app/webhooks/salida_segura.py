"""Salida HTTP segura hacia URLs controladas por el usuario (F-05, webhooks).

El problema clásico: se valida la URL al guardarla (resuelve a una IP pública) y se conecta
después (resuelve otra vez → DNS rebinding a 127.0.0.1 o a la red interna). Aquí:

1. `destino_validado()` resuelve TODAS las direcciones A/AAAA con getaddrinfo y rechaza si
   CUALQUIERA es loopback, privada, de enlace local, multicast, reservada o no global.
2. `enviar()` conecta FIJANDO la IP ya validada (la URL lleva la IP; `Host` y SNI llevan el
   nombre original, así el certificado se comprueba contra el nombre). Sin redirecciones.
3. En producción solo `https://` (WEBHOOKS_PERMITIR_HTTP=1 lo relaja para laboratorio).

Defensa independiente: la política de egreso del sistema (deploy/webmail/nftables/egreso-backend.nft)
impide al proceso del correo llegar a RFC1918/loopback salvo lista blanca.
"""

import ipaddress
import os
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx


class DestinoNoPermitido(ValueError):
    pass


@dataclass
class Destino:
    url_original: str
    host: str
    ip: str
    puerto: int
    esquema: str

    @property
    def url_fijada(self) -> str:
        p = urlsplit(self.url_original)
        ip = f"[{self.ip}]" if ":" in self.ip else self.ip
        netloc = f"{ip}:{self.puerto}"
        return urlunsplit((self.esquema, netloc, p.path or "/", p.query, ""))


def _http_permitido() -> bool:
    if os.getenv("WEBHOOKS_PERMITIR_HTTP", "") == "1":
        return True
    try:
        from app.config import get_settings

        return get_settings().environment.lower() in ("development", "dev", "local")
    except Exception:
        return False


def _ip_prohibida(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    )


def resolver_todas(host: str, puerto: int) -> list[str]:
    """Todas las direcciones a las que puede resolver el nombre (IPv4 e IPv6)."""
    try:
        infos = socket.getaddrinfo(host, puerto, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise DestinoNoPermitido("Hostname no resolvible") from exc
    ips = []
    for _familia, _tipo, _proto, _canon, sockaddr in infos:
        ip = sockaddr[0]
        if ip not in ips:
            ips.append(ip)
    if not ips:
        raise DestinoNoPermitido("Hostname sin direcciones")
    return ips


def destino_validado(url: str) -> Destino:
    """Valida esquema, nombre y TODAS sus direcciones; devuelve el destino con la IP fijada."""
    p = urlsplit(url)
    if p.scheme not in ("https", "http"):
        raise DestinoNoPermitido("Solo se permiten URLs HTTP/HTTPS")
    if p.scheme == "http" and not _http_permitido():
        raise DestinoNoPermitido("En producción solo se permiten webhooks https://")
    if p.username or p.password:
        raise DestinoNoPermitido("URL con credenciales no permitida")
    host = p.hostname
    if not host:
        raise DestinoNoPermitido("URL sin hostname")
    puerto = p.port or (443 if p.scheme == "https" else 80)
    try:
        literal = ipaddress.ip_address(host)
        ips = [str(literal)]
    except ValueError:
        ips = resolver_todas(host, puerto)
    for ip in ips:
        if _ip_prohibida(ipaddress.ip_address(ip)):
            raise DestinoNoPermitido("URL apunta a red interna/privada")
    return Destino(
        url_original=url, host=host, ip=ips[0], puerto=puerto, esquema=p.scheme
    )


async def enviar(
    destino: Destino, contenido: bytes, cabeceras: dict, timeout: float = 10.0
) -> httpx.Response:
    """POST al destino conectando a la IP validada, con Host y SNI del nombre original y sin
    seguir redirecciones (cada salto tendría que volver a validarse)."""
    cab = dict(cabeceras)
    cab["Host"] = (
        destino.host
        if destino.puerto in (80, 443)
        else f"{destino.host}:{destino.puerto}"
    )
    extensiones = {"sni_hostname": destino.host} if destino.esquema == "https" else {}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        return await client.post(
            destino.url_fijada, content=contenido, headers=cab, extensions=extensiones
        )
