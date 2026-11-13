"""Leer una cabecera de un correo sin que una cabecera mal formada tumbe la lista entera.

Con la política moderna de `email`, pedir «To» o «From» analiza las direcciones; si el nombre trae un
salto de línea (correos mal construidos o maliciosos), lanza `ValueError: address parts cannot contain
CR or LF`. Eso ocurría al listar una carpeta: un solo correo así dejaba la carpeta sin poder abrirse
(error 500, 13/11/2026). Aquí, si la lectura falla, se devuelve el texto de la cabecera tal como vino,
en una sola línea.
"""

from __future__ import annotations

import email
import email.policy


def leer(msg, crudo: str, nombre: str) -> str:
    """Valor de la cabecera `nombre`; nunca lanza."""
    try:
        return msg.get(nombre, "") or ""
    except Exception:
        pass
    try:
        valor = email.message_from_string(
            crudo or "", policy=email.policy.compat32
        ).get(nombre, "")
        return " ".join(str(valor or "").split())
    except Exception:
        return ""
