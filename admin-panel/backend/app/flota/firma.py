"""Firma de órdenes de Flota Maquita (T-88).

Par de claves PROPIO de Flota (no el de Raíces: allí las sesiones van con HS256, un secreto compartido
que no se puede entregar a los equipos; ni el certificado Authenticode, que no debe vivir en un servidor
expuesto). ECDSA P-256 + SHA-256, firma en formato IEEE P1363 (r||s, 64 bytes): es el formato por
defecto de `ECDsa.VerifyData` en .NET 8, sin librerías extra en el agente.

Se firman los BYTES exactos de la carga (JSON UTF-8). El agente verifica esos bytes y solo después los
interpreta: no hay canonicalización que pueda desalinearse.

Clave privada: FLOTA_CLAVE_PRIVADA (por defecto /etc/maquita-mail/flota/orden-firma.key), legible
solo por root y el grupo maquita-admin. `kid`: FLOTA_KID (por defecto flota-2026-11).
"""

from __future__ import annotations

import base64
import json
import os
from functools import lru_cache

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

RUTA = os.getenv("FLOTA_CLAVE_PRIVADA", "/etc/maquita-mail/flota/orden-firma.key")
KID = os.getenv("FLOTA_KID", "flota-2026-11")
PROPOSITO = "maquita-flota-orden"


class SinClave(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _privada() -> ec.EllipticCurvePrivateKey:
    try:
        with open(RUTA, "rb") as f:
            clave = serialization.load_pem_private_key(f.read(), password=None)
    except OSError as e:
        raise SinClave(f"no se puede leer la clave de firma de Flota ({RUTA}): {e.strerror}") from e
    if not isinstance(clave, ec.EllipticCurvePrivateKey) or clave.curve.name != "secp256r1":
        raise SinClave("la clave de firma de Flota no es ECDSA P-256")
    return clave


def disponible() -> bool:
    try:
        _privada()
        return True
    except SinClave:
        return False


def publica_pem() -> str:
    return _privada().public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def firmar(carga: dict) -> tuple[str, str]:
    """(carga_b64, firma_b64). `carga` ya trae proposito, v y kid."""
    datos = json.dumps(carga, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    der = _privada().sign(datos, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return base64.b64encode(datos).decode(), base64.b64encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")).decode()


def verificar(carga_b64: str, firma_b64: str) -> bool:
    """Lo mismo que hará el agente; se usa en las pruebas y como comprobación tras firmar."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    firma = base64.b64decode(firma_b64)
    if len(firma) != 64:
        return False
    der = encode_dss_signature(int.from_bytes(firma[:32], "big"), int.from_bytes(firma[32:], "big"))
    try:
        _privada().public_key().verify(der, base64.b64decode(carga_b64), ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False
