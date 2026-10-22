"""Cifrado del client_secret del proveedor de identidad con la llave de credenciales del proyecto.

Es la misma llave dedicada que usa el correo (CREDENTIAL_ENCRYPTION_KEY, formato Fernet, H-02). El panel
la recibe prestada como WEBMAIL_CREDENTIAL_ENCRYPTION_KEY (ver wrappers/entorno_webmail.py); si existe
la anterior (…_ANTERIOR), se descifra con cualquiera de las dos y se cifra siempre con la actual, igual
que en backend/app/core/cifrado.py.
"""

import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class SinLlave(RuntimeError):
    """El panel no tiene la llave de credenciales (o no es una llave Fernet válida)."""


def _llave(*nombres: str) -> str:
    for nombre in nombres:
        valor = (os.environ.get(nombre) or "").strip()
        if valor:
            return valor
    return ""


def _fernet() -> MultiFernet:
    actual = _llave("WEBMAIL_CREDENTIAL_ENCRYPTION_KEY", "CREDENTIAL_ENCRYPTION_KEY")
    anterior = _llave("WEBMAIL_CREDENTIAL_ENCRYPTION_KEY_ANTERIOR", "CREDENTIAL_ENCRYPTION_KEY_ANTERIOR")
    if not actual:
        raise SinLlave("Falta WEBMAIL_CREDENTIAL_ENCRYPTION_KEY en el .env del panel (la misma que "
                       "CREDENTIAL_ENCRYPTION_KEY del correo)")
    try:
        llaves = [Fernet(actual.encode())] + ([Fernet(anterior.encode())] if anterior else [])
    except ValueError:
        raise SinLlave("WEBMAIL_CREDENTIAL_ENCRYPTION_KEY no es una llave Fernet válida")
    return MultiFernet(llaves)


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()


def descifrar(token: str) -> str:
    """Lanza SinLlave si no hay llave, o InvalidToken si se cifró con otra."""
    return _fernet().decrypt(token.encode()).decode()


__all__ = ["SinLlave", "InvalidToken", "cifrar", "descifrar"]
