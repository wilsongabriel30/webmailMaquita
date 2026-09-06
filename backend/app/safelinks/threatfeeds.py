"""Safe Links — inteligencia de amenazas real (feeds gratuitos).

Descarga listas públicas de dominios maliciosos y las guarda en Redis para que la
pasarela de Safe Links bloquee/avise sobre destinos conocidos como peligrosos.

Fuentes (sin API key):
- URLhaus (abuse.ch): hosts con malware -> verdict 'blocked' (alta confianza).
- Phishing.Database (GitHub): dominios de phishing activos -> 'suspicious' (avisa).

Se refresca al arrancar y cada 12 h (tarea en segundo plano).
"""
from __future__ import annotations

import asyncio
import json
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

URLHAUS = "https://urlhaus.abuse.ch/downloads/hostfile/"
PHISHDB = "https://raw.githubusercontent.com/mitchellkrogza/Phishing.Database/master/phishing-domains-ACTIVE.txt"

KEY_MALWARE = "tintel:malware"
KEY_PHISH = "tintel:phish"


def _download(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Maquita-SafeLinks/1.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def _hosts_urlhaus(text: str) -> set:
    out = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            h = parts[1].strip().lower().rstrip(".")
            if "." in h and h != "localhost":
                out.add(h)
    return out


def _hosts_domainlist(text: str) -> set:
    out = set()
    for line in text.splitlines():
        line = line.strip().lower().rstrip(".")
        if not line or line.startswith("#"):
            continue
        if "/" in line or "://" in line:
            try:
                line = urlparse(line if "://" in line else "http://" + line).hostname or ""
            except Exception:
                continue
        if line and "." in line and " " not in line:
            out.add(line)
    return out


async def _store(redis, key: str, hosts: set):
    try:
        await redis.delete(key)
        hl = list(hosts)
        for i in range(0, len(hl), 5000):
            await redis.sadd(key, *hl[i:i + 5000])
    except Exception:
        pass


async def refresh(redis, db=None) -> dict:
    sources = {}
    malware, phish = set(), set()
    try:
        malware = _hosts_urlhaus(await asyncio.to_thread(_download, URLHAUS))
        sources["URLhaus"] = len(malware)
    except Exception:
        sources["URLhaus"] = "error"
    try:
        phish = _hosts_domainlist(await asyncio.to_thread(_download, PHISHDB))
        sources["Phishing.Database"] = len(phish)
    except Exception:
        sources["Phishing.Database"] = "error"

    if malware:
        await _store(redis, KEY_MALWARE, malware)
    if phish:
        await _store(redis, KEY_PHISH, phish)

    if db is not None and (malware or phish):
        try:
            await db.execute(
                "INSERT INTO threat_feed_meta (id, malware_count, phish_count, sources, updated_at) "
                "VALUES (1,$1,$2,$3,$4) ON CONFLICT (id) DO UPDATE SET "
                "malware_count=EXCLUDED.malware_count, phish_count=EXCLUDED.phish_count, "
                "sources=EXCLUDED.sources, updated_at=EXCLUDED.updated_at",
                len(malware), len(phish), json.dumps(sources), datetime.now(timezone.utc))
        except Exception:
            pass
    return {"ok": bool(malware or phish), "malware": len(malware), "phish": len(phish), "sources": sources}


async def classify(redis, host: str, registrable: str = ""):
    """Devuelve (verdict, reason) si el host/dominio está en algún feed; si no, None."""
    if not host:
        return None
    cands = [host]
    if registrable and registrable != host:
        cands.append(registrable)
    try:
        for h in cands:
            if await redis.sismember(KEY_MALWARE, h):
                return ("suspicious", "Dominio reportado con malware (URLhaus) — verifica antes de continuar")
        for h in cands:
            if await redis.sismember(KEY_PHISH, h):
                return ("suspicious", "Dominio reportado como phishing (base de datos de amenazas)")
    except Exception:
        pass
    return None


async def loop(app):
    """Refresco periódico (arranque + cada 12 h)."""
    await asyncio.sleep(15)  # dar tiempo a que arranque la app
    while True:
        try:
            await refresh(app.state.redis, app.state.db_pool)
        except Exception:
            pass
        await asyncio.sleep(43200)  # 12 h
