"""Adjuntos de los borradores.

Un borrador se reemplaza entero en cada guardado automático (APPEND nuevo + borrar el
anterior), así que sus adjuntos deben ir en cada guardado. Para no reenviar megas cada 30 s,
el redactor manda los archivos solo cuando cambian y, el resto de veces, pide conservar
los del borrador anterior (`mantener_adjuntos`), que aquí se copian del mensaje guardado.
"""

import base64
import email
import email.policy

from app.mail.clients.imap_client import fetch_raw_message
from app.mail.clients.smtp_client import EmailAttachment

LIMITE_TOTAL = 25 * 1024 * 1024  # mismo tope que el envío


def adjuntos_desde_peticion(atts) -> list[EmailAttachment]:
    """Decodifica los adjuntos base64 de la petición; corta al superar el límite total."""
    resultado: list[EmailAttachment] = []
    total = 0
    for att in atts or []:
        try:
            contenido = base64.b64decode(att.content_b64)
        except Exception:
            continue
        total += len(contenido)
        if total > LIMITE_TOTAL:
            break
        resultado.append(
            EmailAttachment(
                filename=att.filename,
                content=contenido,
                content_type=att.content_type or "application/octet-stream",
                is_inline=bool(att.is_inline),
                cid=att.cid or "",
            )
        )
    return resultado


async def adjuntos_del_borrador_anterior(
    imap, uid: int, carpeta: str = "Drafts"
) -> list[EmailAttachment]:
    """Devuelve los adjuntos (no incrustados) del borrador guardado con ese UID.

    Nota para revisores: `imap` es la sesion IMAP de la propia persona (o de la cuenta delegada ya
    autorizada) y `fetch_raw_message` hace SELECT de la carpeta antes del UID FETCH: no es posible
    leer borradores de otras cuentas por UID. Ver docs/REVISIONES-DE-SEGURIDAD.md.
    """
    try:
        raw = await fetch_raw_message(imap, carpeta, uid)
    except Exception:
        raw = None
    if not raw:
        return []
    if isinstance(raw, str):
        raw = raw.encode("utf-8", "surrogateescape")
    try:
        msg = email.message_from_bytes(raw, policy=email.policy.default)
    except Exception:
        return []
    resultado: list[EmailAttachment] = []
    for parte in msg.iter_attachments():
        nombre = parte.get_filename()
        if not nombre:
            continue
        contenido = parte.get_payload(decode=True) or b""
        resultado.append(
            EmailAttachment(
                filename=nombre,
                content=contenido,
                content_type=parte.get_content_type() or "application/octet-stream",
                is_inline=False,
                cid="",
            )
        )
    return resultado
