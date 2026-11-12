"""Alta rápida de un contacto desde un correo (el «+» junto al remitente): qué hacer si ya existe.

Muchos contactos nacen solos del historial de enviados, sin nombre (queda el propio correo como
nombre) o con el nombre de quien usaba antes esa dirección. Pulsar «+» respondía «ya existe» y no
cambiaba nada: la persona no encontraba el contacto por su nombre ni podía corregirlo (12/11/2026).

Regla:
  - el contacto no tiene un nombre útil            → se completa con el del correo («completar»);
  - tiene el mismo nombre                          → nada que hacer («igual»);
  - tiene OTRO nombre                              → se pregunta («distinto») y solo se cambia
                                                     si la persona lo confirma («actualizar»).
Funciones puras, sin base de datos.
"""

from __future__ import annotations

import unicodedata


def _plano(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto or "")
    return " ".join(
        "".join(c for c in sin_tildes if not unicodedata.combining(c))
        .casefold()
        .split()
    )


def nombre_util(nombre: str | None, email: str) -> str:
    """El nombre, o «» si en realidad no dice quién es (vacío, el correo o su parte local)."""
    nombre = " ".join((nombre or "").replace('"', "").replace("'", "").split())
    correo = (email or "").strip().lower()
    if not nombre or "@" in nombre or nombre.lower() in (correo, correo.split("@")[0]):
        return ""
    return nombre[:255]


def decidir(
    nombre_guardado: str | None,
    email: str,
    nombre_del_correo: str | None,
    confirmado: bool = False,
) -> str:
    nuevo = nombre_util(nombre_del_correo, email)
    if not nuevo:
        return "igual"
    guardado = nombre_util(nombre_guardado, email)
    if not guardado:
        return "completar"
    if _plano(guardado) == _plano(nuevo):
        return "igual"
    return "actualizar" if confirmado else "distinto"


def partir(nombre: str) -> tuple[str, str]:
    """Nombre y apellido aproximados para los campos separados (la persona puede corregirlos después)."""
    partes = nombre.split()
    if len(partes) <= 1:
        return (nombre[:100], "")
    return (partes[0][:100], " ".join(partes[1:])[:100])
