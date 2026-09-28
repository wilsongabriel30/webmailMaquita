"""Alcance: cada operación comprueba que la dirección es de un dominio asignado.

Responde 404 y no 403: a un administrador de dominio no se le confirma si una dirección
de otro dominio existe.
"""

from fastapi import HTTPException


def exigir_alcance(admin: dict, direccion: str) -> str:
    direccion = str(direccion or "")
    if direccion.count("@") != 1:
        raise HTTPException(404, "No encontrado")
    dominio = direccion.split("@")[1].lower()
    if not dominio or dominio not in admin["dominios"]:
        raise HTTPException(404, "No encontrado")
    return dominio
