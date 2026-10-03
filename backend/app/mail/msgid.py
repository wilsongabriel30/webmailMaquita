"""Message-ID de los correos que salen del webmail."""

from email.utils import make_msgid, parseaddr


def msgid_del_remitente(remitente: str, dominio_por_defecto: str) -> str:
    """Message-ID con el dominio de quien envía.

    En un servidor con varias empresas, usar el dominio del servidor hace que los mensajes
    de un cliente salgan con el Message-ID de otro dominio. Si el remitente no trae un
    dominio utilizable, se usa el del servidor.
    """
    direccion = parseaddr(remitente or "")[1]
    dominio = direccion.rsplit("@", 1)[1].strip().lower() if "@" in direccion else ""
    if not dominio or any(c.isspace() or c in "<>" for c in dominio):
        dominio = dominio_por_defecto
    return make_msgid(domain=dominio)
