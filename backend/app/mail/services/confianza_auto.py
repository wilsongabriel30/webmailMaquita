"""«No es spam» deja al remitente en confianza.

Cuando alguien saca un correo de «Correo no deseado», está diciendo que ese remitente es legítimo
para él. Antes solo se movía el mensaje y se entrenaba al filtro estadístico; el siguiente correo
del mismo remitente podía volver a caer (los filtros por reglas no aprenden) y la persona tenía que
rescatarlo otra vez. Ahora el remitente pasa a su lista de remitentes de confianza.
"""

import re
from email import message_from_bytes
from email.utils import parseaddr

_CORREO = re.compile(r"^[^@\s<>\"]{1,64}@[a-z0-9.-]{1,255}$", re.I)


def remitentes_de(mensajes_crudos, propio: str = "") -> list[str]:
    """Direcciones del «From» de cada mensaje, sin repetir y sin la del propio usuario.

    La propia se excluye a propósito: un correo que suplanta al usuario no debe servir para que
    todo lo que diga venir de él salte el filtro.
    """
    propio = (propio or "").strip().lower()
    vistos: list[str] = []
    for crudo in mensajes_crudos:
        try:
            direccion = (
                parseaddr(str(message_from_bytes(crudo).get("From", "")))[1]
                .strip()
                .lower()
            )
        except Exception:
            continue
        if (
            direccion
            and direccion != propio
            and _CORREO.match(direccion)
            and direccion not in vistos
        ):
            vistos.append(direccion)
    return vistos


def fusionar(actuales: list[str], nuevos: list[str], maximo: int) -> list[str]:
    """Lista resultante, ordenada; no pasa del máximo (los nuevos que no quepan se omiten)."""
    resultado = list(dict.fromkeys(a.strip().lower() for a in actuales if a))
    for n in nuevos:
        if n not in resultado and len(resultado) < maximo:
            resultado.append(n)
    return sorted(resultado)
