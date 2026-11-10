"""Códigos de alta y secreto del equipo (T-88).

Código de alta: `MQF-XXXX-XXXX-XXXX` (12 símbolos Crockford base32 = 60 bits), un uso, lo crea el panel.
Se acepta en minúsculas, sin guiones y con O/I/L confundidas. En la base solo queda su SHA-256.

Secreto del equipo: 43 caracteres base64url (256 bits), se entrega UNA vez al enrolar; el agente lo manda
en la cabecera `X-Flota-Secreto`. En la base solo queda su SHA-256.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_EQUIVALENCIAS = str.maketrans({"O": "0", "I": "1", "L": "1"})
FORMATO_SECRETO = re.compile(r"^[A-Za-z0-9_-]{43}$")


def normalizar_codigo(texto: str) -> str | None:
    """`mqf-abcd-efgh-jk1m` → `ABCDEFGHJK1M` (sin prefijo ni guiones) o None si no tiene forma de código."""
    t = re.sub(r"[\s-]", "", str(texto or "")).upper()
    if t.startswith("MQF"):
        t = t[3:]
    t = t.translate(_EQUIVALENCIAS)
    if len(t) != 12 or any(c not in _CROCKFORD for c in t):
        return None
    return t


def huella(valor: str) -> str:
    return hashlib.sha256(valor.encode()).hexdigest()


def nuevo_secreto() -> str:
    return secrets.token_urlsafe(32)


def secreto_valido(secreto: str, hash_guardado: str) -> bool:
    if not FORMATO_SECRETO.match(secreto or ""):
        return False
    return hmac.compare_digest(huella(secreto), hash_guardado or "")
