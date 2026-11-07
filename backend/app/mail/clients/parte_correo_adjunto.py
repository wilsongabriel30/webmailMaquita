"""Un correo adjunto (.eml) se anida como parte message/rfc822 de verdad (05/11/2026).

RFC 2046 §5.2.1: una parte message/rfc822 solo admite 7bit, 8bit o binary. Antes el .eml salía
en base64 como cualquier archivo; Dovecot (BINARY.PEEK) lo devolvía sin decodificar y la
descarga y la vista previa mostraban texto base64 con tamaño 0. Anidado como mensaje,
Outlook, Gmail y este webmail lo muestran como un correo dentro del correo.
"""

import email
from email import policy
from email.mime.message import MIMEMessage


def es_correo_adjunto(content_type: str) -> bool:
    return (content_type or "").split(";", 1)[0].strip().lower() == "message/rfc822"


def construir_parte_correo(contenido: bytes) -> MIMEMessage | None:
    """Parte message/rfc822 con el correo anidado, o None si el contenido no parece un correo."""
    try:
        interno = email.message_from_bytes(contenido or b"", policy=policy.compat32)
    except Exception:
        return None
    if not interno.keys():
        return None
    return MIMEMessage(interno)
