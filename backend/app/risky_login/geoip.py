"""Geolocalización de IPs para detección de logins riesgosos.

IPs internas/propias (LAN, VPN, rango 193.16.0.0/24) se tratan como confiables y
NO se geolocalizan. Las públicas se resuelven con una BASE LOCAL (DB-IP City Lite,
formato MaxMind) que vive en el servidor; se cachea en Redis 30 días para no repetir
la misma búsqueda.

Antes esto consultaba ip-api.com por HTTP **sin cifrar**: cada inicio de sesión
publicaba a un tercero la IP de quien entraba, y cualquiera en el camino podía leer
esas consultas o falsear la respuesta para disimular un acceso desde otro país, que
es justo lo que este módulo debe detectar. Ahora no sale ninguna petición. [T4]

La base se actualiza con `actualizar-geoip.sh` (temporizador mensual). Si falta el
archivo, la geolocalización devuelve vacío y el resto del análisis de riesgo sigue.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import threading

# Redes propias/confiables (su LAN usa el bloque público 193.16.0.0/24)
_TRUSTED = [
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "100.64.0.0/10",
        "193.16.0.0/24",
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


BASE_GEOIP = os.getenv("GEOIP_DB", "/var/lib/GeoIP/dbip-city-lite.mmdb")

_log = logging.getLogger(__name__)
_lector = None
_lector_lock = threading.Lock()


def _abrir_base():
    """Abre la base local una sola vez y la reutiliza (el lector es seguro entre hilos)."""
    global _lector
    if _lector is not None:
        return _lector
    with _lector_lock:
        if _lector is None:
            try:
                import maxminddb

                _lector = maxminddb.open_database(BASE_GEOIP)
            except FileNotFoundError:
                _log.warning(
                    "Sin base GeoIP en %s: la geolocalización queda vacía", BASE_GEOIP
                )
                return None
            except Exception as e:
                _log.warning("No se pudo abrir la base GeoIP (%s): %s", BASE_GEOIP, e)
                return None
    return _lector


def _nombre(bloque: dict) -> str:
    """Nombre en español si la base lo trae; si no, en inglés."""
    nombres = (bloque or {}).get("names") or {}
    return nombres.get("es") or nombres.get("en") or ""


def _fetch(ip: str) -> dict:
    """Consulta la base LOCAL. Sin red: ni un paquete sale de la organización."""
    lector = _abrir_base()
    if lector is None:
        return {}
    try:
        d = lector.get(ip) or {}
    except (ValueError, TypeError):
        return {}
    if not d:
        return {}
    ubic = d.get("location") or {}
    pais = _nombre(d.get("country"))
    ciudad = _nombre(d.get("city"))
    if not pais and not ciudad and ubic.get("latitude") is None:
        return {}
    return {
        "country": pais,
        "city": ciudad,
        "lat": ubic.get("latitude"),
        "lon": ubic.get("longitude"),
    }


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
