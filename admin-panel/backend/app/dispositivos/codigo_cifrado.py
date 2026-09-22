"""Código de enrolamiento asignado a una persona: cifrado recuperable (22/09/2026).

Decisión de dirección: el código lo crea solo Tecnología desde el panel, asignado a una persona; esa
persona puede volver a verlo en su Configuración del correo y la app lo recibe para activar con un
toque. Para eso el código en claro se guarda cifrado con Fernet usando `DISP_CODIGO_CLAVE` (variable
del `.env` del backend y del panel, la misma en ambos; nunca en la base). Se descifra únicamente para
el custodio autenticado (su sesión ya pasó el segundo factor si lo tiene) y para administradores del
panel, y cada lectura queda en `admin_audit`. El registro cifrado se borra al agotarse, caducar o
anularse el código. Sin clave configurada no se guarda nada en claro (vuelve al «solo una vez»).

Generar la clave: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os
import re

from cryptography.fernet import Fernet, InvalidToken

_VARIABLE = "DISP_CODIGO_CLAVE"
_FORMATO = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}$")


def _fernet() -> Fernet | None:
    clave = (os.environ.get(_VARIABLE) or "").strip()
    if not clave:
        return None
    try:
        return Fernet(clave.encode())
    except Exception:
        return None


def disponible() -> bool:
    return _fernet() is not None


def cifrar(codigo_claro: str) -> str | None:
    """Devuelve el código cifrado o None si no hay clave (entonces no se guarda en claro)."""
    f = _fernet()
    return f.encrypt(codigo_claro.encode()).decode() if f else None


def descifrar(cifrado: str | None) -> str | None:
    """Código en formato xxxx-xxxx-xxxx, o None si no hay registro, clave o el token no es válido."""
    f = _fernet()
    if not f or not cifrado:
        return None
    try:
        claro = f.decrypt(cifrado.encode()).decode()
    except InvalidToken:
        return None
    return claro if _FORMATO.match(claro) else None
