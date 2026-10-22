"""País de una IP con la base GeoIP LOCAL del servidor (la misma que usa la detección de inicios de
sesión riesgosos del correo: DB-IP City Lite, formato MaxMind, actualizada cada mes por
actualizar-geoip.sh). Sin red: ninguna IP sale del servidor. Sin base, el país queda «--».

Devuelve el código ISO-2 (el panel lo muestra con su nombre en español), «LAN» para la red interna
(privadas y ORG_REDES) y «--» si no se sabe. No se resuelve el ASN: la base libre no lo trae.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re

_log = logging.getLogger(__name__)
BASE = os.getenv("GEOIP_DB", "/var/lib/GeoIP/dbip-city-lite.mmdb")
_PRIVADAS = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16", "100.64.0.0/10")
_RE_ISO = re.compile(r"[A-Z]{2}")


class Geo:
    def __init__(self, redes_propias=(), base: str = BASE, lector=None):
        self._redes = []
        for t in list(_PRIVADAS) + list(redes_propias):
            try:
                self._redes.append(ipaddress.ip_network(t, strict=False))
            except ValueError:
                _log.warning("ORG_REDES: «%s» no es una red válida; se ignora", t)
        self._lector = lector
        if self._lector is None:
            try:
                import maxminddb

                self._lector = maxminddb.open_database(base)
            except Exception as e:  # sin la biblioteca o sin la base: el resto sigue
                _log.warning("Sin base GeoIP (%s): los países quedan sin resolver", e)
        self._cache: dict = {}

    def es_interna(self, ip: str) -> bool:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if a.version == 6:
            return a.is_private or a.is_loopback or a.is_link_local
        return any(a in r for r in self._redes if r.version == 4)

    def pais(self, ip: str) -> str:
        if not ip:
            return "--"
        if ip in self._cache:
            return self._cache[ip]
        if self.es_interna(ip):
            codigo = "LAN"
        else:
            codigo = "--"
            if self._lector is not None:
                try:
                    d = self._lector.get(ip) or {}
                    iso = ((d.get("country") or {}).get("iso_code") or "").upper()
                    if _RE_ISO.fullmatch(iso):
                        codigo = iso
                except (ValueError, TypeError):
                    pass
        if len(self._cache) < 50000:
            self._cache[ip] = codigo
        return codigo
