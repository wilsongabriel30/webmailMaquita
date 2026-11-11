"""Localizar y llamar por HTTPS al servidor de correo de otro dominio.

El servidor de un dominio es el de su registro MX; se le habla por HTTPS con certificado válido,
sin seguir redirecciones. Para que nadie use esto como trampolín hacia la red interna, solo se
llama a direcciones públicas, salvo los nombres listados en `RECALL_FEDERADO_HOSTS_INTERNOS`
(servidores hermanos alcanzables por la red privada).
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket

import httpx

from app.config import get_settings

logger = logging.getLogger("maquita.webmail.federacion")

TIEMPO_S = 8.0
MAX_SERVIDORES = 2
_NOMBRE = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)


def nombre_valido(host: str) -> bool:
    return bool(_NOMBRE.match((host or "").lower()))


def hosts_internos() -> set[str]:
    crudo = getattr(get_settings(), "recall_federado_hosts_internos", "") or ""
    return {h.strip().lower() for h in crudo.split(",") if h.strip()}


def _mx(dominio: str) -> list[str]:
    try:
        import dns.resolver

        respuesta = dns.resolver.resolve(dominio, "MX", lifetime=5)
    except Exception:
        # Sin respuesta (o sin dnspython instalado): ese dominio se trata como no compatible.
        return []
    pares = sorted(
        (r.preference, str(r.exchange).rstrip(".").lower()) for r in respuesta
    )
    return [host for _, host in pares if nombre_valido(host)]


async def servidores_de(dominio: str) -> list[str]:
    """Hosts MX del dominio, por prioridad (como mucho los dos primeros)."""
    dominio = (dominio or "").strip().lower()
    if not nombre_valido(dominio):
        return []
    return (await asyncio.to_thread(_mx, dominio))[:MAX_SERVIDORES]


def _ips(host: str) -> list[str]:
    try:
        return sorted(
            {i[4][0] for i in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        )
    except OSError:
        return []


def ip_publica(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


async def host_permitido(host: str) -> bool:
    host = (host or "").lower()
    if not nombre_valido(host):
        return False
    if host in hosts_internos():
        return True
    ips = await asyncio.to_thread(_ips, host)
    return bool(ips) and all(ip_publica(ip) for ip in ips)


async def llamar(
    host: str,
    metodo: str,
    ruta: str,
    cuerpo: dict | None = None,
    tiempo_s: float = TIEMPO_S,
) -> dict | None:
    """Respuesta JSON (dict) del otro servidor, o None ante cualquier problema."""
    if not await host_permitido(host):
        return None
    try:
        async with httpx.AsyncClient(
            timeout=tiempo_s,
            follow_redirects=False,
            headers={"User-Agent": "recuperacion-correo/1"},
        ) as cliente:
            r = await cliente.request(metodo, f"https://{host}{ruta}", json=cuerpo)
        if r.status_code != 200:
            return None
        datos = r.json()
        return datos if isinstance(datos, dict) else None
    except Exception as exc:
        logger.info("federación: %s %s%s no respondió: %s", metodo, host, ruta, exc)
        return None
