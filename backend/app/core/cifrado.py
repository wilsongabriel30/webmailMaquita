"""Cifrado de credenciales con llave DEDICADA y versionada (H-02 / L-03, cuarta revisión).

Antes la llave Fernet se derivaba de SECRET_KEY (la que firma los JWT): comprometer una
comprometía la otra, y rotar SECRET_KEY rompía todo lo cifrado sin aviso. Ahora:

- `CREDENTIAL_ENCRYPTION_KEY` (obligatoria, formato de llave Fernet) cifra la credencial IMAP
  cacheada en Redis, las credenciales de Nextcloud guardadas en la base y el secreto TOTP.
- `CREDENTIAL_ENCRYPTION_KEY_ANTERIOR` (opcional) permite rotar: se descifra con cualquiera de
  las dos y se cifra siempre con la actual (`MultiFernet`). `deploy/tools/recifrar-credenciales.py`
  vuelve a cifrar lo guardado en la base con la llave actual.

Generar una llave: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet  # noqa: F401

from app.config import get_settings


def _fernets() -> list[Fernet]:
    s = get_settings()
    llaves = [Fernet(s.credential_encryption_key.encode())]
    if (s.credential_encryption_key_anterior or "").strip():
        llaves.append(Fernet(s.credential_encryption_key_anterior.strip().encode()))
    return llaves


def cifrar(texto: str) -> str:
    return MultiFernet(_fernets()).encrypt(texto.encode()).decode()


def descifrar(token: str) -> str:
    """Descifra con la llave actual o la anterior. Lanza InvalidToken si no es de ninguna."""
    return MultiFernet(_fernets()).decrypt(token.encode()).decode()


def recifrar(token: str) -> str:
    """Devuelve el mismo secreto cifrado con la llave ACTUAL (para la rotación)."""
    return MultiFernet(_fernets()).rotate(token.encode()).decode()


def esta_cifrado(valor: str | None) -> bool:
    """Un token Fernet empieza siempre por la versión 0x80 en base64 urlsafe: 'gAAAA'."""
    return bool(valor) and str(valor).startswith("gAAAA")


def fernet_heredado_de_secret_key() -> Fernet:
    """La llave ANTIGUA (derivada de SECRET_KEY). Solo para migrar lo que quedó cifrado con
    ella: no se usa para cifrar nada nuevo."""
    clave = hashlib.sha256(get_settings().secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(clave))
