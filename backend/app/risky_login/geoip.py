"""Geolocalización de IPs para detección de logins riesgosos.

IPs internas/propias (LAN, VPN, rango 193.16.0.0/24) se tratan como confiables y
NO se geolocalizan. Las públicas se resuelven con ip-api.com (gratis) y se cachean
en Redis 30 días para no exceder el límite y no consultar lo mismo dos veces.
"""
from __future__ import annotations
import asyncio
import ipaddress
import json
import urllib.request

# Redes propias/confiables (su LAN usa el bloque público 193.16.0.0/24)
_TRUSTED = [
    ipaddress.ip_network(n) for n in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8",
        "169.254.0.0/16", "100.64.0.0/10", "193.16.0.0/24",
    )
]


def is_internal(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return True  # IP inválida/vacía -> tratar como interna (sin riesgo)
    if addr.version == 6:
        return addr.is_private or addr.is_loopback or addr.is_link_local
    return any(addr in net for net in _TRUSTED)


def _fetch(ip: str) -> dict:
    url = f"http://ip-api.com/json/{ip}?fields=status,country,city,lat,lon&lang=es"
    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            d = json.loads(r.read().decode())
        if d.get("status") == "success":
            return {"country": d.get("country", ""), "city": d.get("city", ""),
                    "lat": d.get("lat"), "lon": d.get("lon")}
    except Exception:
        pass
    return {}


async def geolocate(redis, ip: str) -> dict:
    """Devuelve {internal} o {country, city, lat, lon}. Cachea en Redis."""
    if is_internal(ip):
        return {"internal": True}
    key = f"geoip:{ip}"
    try:
        cached = await redis.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        cached = None
    geo = await asyncio.to_thread(_fetch, ip)
    if geo:
        try:
            await redis.set(key, json.dumps(geo), ex=2592000)  # 30 días
        except Exception:
            pass
    return geo
