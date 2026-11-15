"""Claves ed25519 del túnel de soporte: comprobar la que se pega a mano (Fase A) y generar el par de un
equipo (Fase B). La clave privada solo viaja dentro de la carga firmada de la orden: aquí nunca se
escribe en disco ni en el registro; para la auditoría se usa su huella pública (SHA256, como `ssh-keygen -l`).
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

_INICIO = "-----BEGIN OPENSSH PRIVATE KEY-----"
_FIN = "-----END OPENSSH PRIVATE KEY-----"
MAX_CLAVE = 4096


def _publica(clave: Ed25519PrivateKey) -> str:
    return (
        clave.public_key()
        .public_bytes(
            serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
        )
        .decode()
    )


def huella(publica: str) -> str:
    """Huella de una clave pública OpenSSH («ssh-ed25519 AAAA…»)."""
    crudo = base64.b64decode(publica.split()[1])
    return "SHA256:" + base64.b64encode(hashlib.sha256(crudo).digest()).decode().rstrip(
        "="
    )


def comprobar(valor) -> tuple[str, str] | None:
    """Clave privada pegada a mano → (clave normalizada, huella pública). Vacío → None.

    Debe ser ed25519, en formato OpenSSH y sin contraseña (el agente la usa sin nadie delante). Los
    mensajes de error nunca repiten lo recibido."""
    if valor is None or not str(valor).strip():
        return None
    texto = str(valor).replace("\r\n", "\n").replace("\r", "\n").strip()
    if (
        len(texto) > MAX_CLAVE
        or not texto.startswith(_INICIO)
        or not texto.endswith(_FIN)
    ):
        raise HTTPException(
            400,
            "La clave del túnel debe ser una clave privada OpenSSH completa (desde la línea BEGIN hasta la línea END).",
        )
    try:
        clave = serialization.load_ssh_private_key(texto.encode(), password=None)
    except Exception:
        raise HTTPException(
            400,
            "No se pudo leer la clave del túnel: debe ser ed25519, en formato OpenSSH y sin contraseña.",
        ) from None
    if not isinstance(clave, Ed25519PrivateKey):
        raise HTTPException(400, "La clave del túnel debe ser de tipo ed25519.")
    return texto + "\n", huella(_publica(clave))


def generar() -> tuple[str, str, str]:
    """Par nuevo para un equipo → (privada OpenSSH, pública «ssh-ed25519 AAAA…», huella)."""
    clave = Ed25519PrivateKey.generate()
    privada = clave.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    ).decode()
    publica = _publica(clave)
    return privada, publica, huella(publica)
