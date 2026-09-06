"""Cifrado de mensajes seguros — AES-256-GCM con clave maestra del servidor.

La clave vive solo en el .env (SECURE_MSG_KEY). El contenido se guarda cifrado
en la BD; sin la clave del servidor no se puede leer aunque se filtre la BD.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings


def _key() -> bytes:
    raw = (get_settings().secure_msg_key or "").strip()
    if not raw:
        raise RuntimeError("SECURE_MSG_KEY no configurada en .env")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError("SECURE_MSG_KEY debe ser de 32 bytes (base64)")
    return key


def encrypt(plaintext: bytes) -> tuple[str, str]:
    """Devuelve (ciphertext_b64, nonce_b64)."""
    nonce = os.urandom(12)
    ct = AESGCM(_key()).encrypt(nonce, plaintext, None)
    return base64.b64encode(ct).decode(), base64.b64encode(nonce).decode()


def decrypt(ct_b64: str, nonce_b64: str) -> bytes:
    ct = base64.b64decode(ct_b64)
    nonce = base64.b64decode(nonce_b64)
    return AESGCM(_key()).decrypt(nonce, ct, None)
