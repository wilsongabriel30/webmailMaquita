"""Safe Links — análisis de reputación de una URL (heurístico, sin depender de
servicios externos). Devuelve un veredicto: safe | suspicious | blocked, con la
razón. Pensado para atrapar phishing común (homógrafos, marcas suplantadas,
IP literales, credenciales en URL, acortadores, etc.).
"""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import unquote, urlparse

# Marcas frecuentemente suplantadas (si aparecen en el host pero el dominio
# registrable NO es el oficial -> sospechoso).
BRANDS = {
    "paypal": "paypal.com", "microsoft": "microsoft.com", "office365": "office.com",
    "outlook": "outlook.com", "google": "google.com", "gmail": "google.com",
    "apple": "apple.com", "icloud": "apple.com", "amazon": "amazon.com",
    "facebook": "facebook.com", "instagram": "instagram.com", "whatsapp": "whatsapp.com",
    "netflix": "netflix.com", "bancopichincha": "pichincha.com", "produbanco": "produbanco.com",
    "bancoguayaquil": "bancoguayaquil.com", "sri": "sri.gob.ec", "maquita": "maquita.com.ec",
}

SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly",
    "cutt.ly", "rb.gy", "shorturl.at", "rebrand.ly", "t.ly",
}

_PUBLIC_SUFFIX2 = {"com", "net", "org", "gob", "edu", "gov", "co", "mil"}


def _registrable(host: str) -> str:
    """Aproximación del dominio registrable (sin lista PSL completa)."""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    # maneja segundos niveles tipo .com.ec / .gob.ec
    if parts[-2] in _PUBLIC_SUFFIX2 and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def analyze(url: str) -> dict:
    """Devuelve {verdict, reason, host}. verdict: safe|suspicious (blocked lo
    decide el servicio con la lista negra de la BD)."""
    raw = (url or "").strip()
    if not raw:
        return {"verdict": "suspicious", "reason": "URL vacía", "host": ""}
    try:
        u = urlparse(raw if "://" in raw else "http://" + raw)
    except Exception:
        return {"verdict": "suspicious", "reason": "URL no válida", "host": ""}

    host = (u.hostname or "").lower()
    if not host:
        return {"verdict": "suspicious", "reason": "Sin dominio", "host": ""}

    # Credenciales embebidas: http://banco.com@evil.com
    if "@" in (u.netloc or ""):
        return {"verdict": "suspicious", "reason": "La dirección esconde el destino real (usa @)", "host": host}

    # IP literal en vez de dominio
    try:
        ipaddress.ip_address(host)
        return {"verdict": "suspicious", "reason": "El enlace apunta a una IP, no a un sitio con nombre", "host": host}
    except ValueError:
        pass

    # Punycode / posibles homógrafos
    if "xn--" in host:
        return {"verdict": "suspicious", "reason": "El dominio usa caracteres internacionales (posible imitación)", "host": host}

    reg = _registrable(host)

    # Suplantación de marca: marca en el host pero dominio registrable distinto
    hostflat = host.replace("-", "").replace(".", "")
    for brand, official in BRANDS.items():
        if brand in hostflat and not (reg == official or reg.endswith("." + official) or reg == _registrable(official)):
            return {"verdict": "suspicious",
                    "reason": f"Imita a «{brand}» pero el dominio real es {reg}", "host": host}

    # Acortadores (ocultan el destino)
    if reg in SHORTENERS:
        return {"verdict": "suspicious", "reason": f"Es un acortador ({reg}); el destino real está oculto", "host": host}

    # Demasiados subdominios (típico de phishing)
    if host.count(".") >= 5:
        return {"verdict": "suspicious", "reason": "El dominio tiene una estructura inusual (muchos subdominios)", "host": host}

    return {"verdict": "safe", "reason": "", "host": host}
