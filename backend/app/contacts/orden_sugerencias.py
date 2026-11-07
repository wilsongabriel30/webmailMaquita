"""Orden final de las sugerencias de destinatario (autocompletado al escribir un correo).

06/11/2026: al escribir un nombre la primera opción debe ser la dirección oficial
(p. ej. usuario@example.org) y no un contacto personal con otra dirección.
Grupos: 1) buzones activos del dominio oficial (ORG_DOMINIO_OFICIAL), 2) resto de direcciones de los dominios propios,
3) listas personales, 4) direcciones externas. Dentro de cada grupo se respeta el orden de
search.py (favoritos, uso frecuente, nombre).
"""

from app import organizacion


def _grupo(contacto: dict, principal: str, propios: frozenset, activos: set) -> int:
    if contacto.get("source") == "list":
        return 2
    email = (contacto.get("email") or "").lower()
    dominio = email.rsplit("@", 1)[-1] if "@" in email else ""
    if dominio == principal and email in activos:
        return 0
    if dominio in propios:
        return 1
    return 3


def ordenar(contactos: list, activos: set, limite: int, usuario: str = "") -> list:
    # Dominio oficial: ORG_DOMINIO_OFICIAL o, si no está, el de quien escribe. NO el de la
    # configuración del servidor (ORG_DOMINIO), que puede ser otro dominio de la casa.
    dominio_usuario = usuario.rsplit("@", 1)[-1].lower() if "@" in usuario else ""
    principal = (
        organizacion.valor("ORG_DOMINIO_OFICIAL", "").lower()
        or dominio_usuario
        or organizacion.dominio_principal()
    )
    propios = organizacion.dominios_propios()
    activos = {a.lower() for a in activos}
    orden = sorted(
        enumerate(contactos),
        key=lambda t: (_grupo(t[1], principal, propios, activos), t[0]),
    )
    return [c for _, c in orden][:limite]
