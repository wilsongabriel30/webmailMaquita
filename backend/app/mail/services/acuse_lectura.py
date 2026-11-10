"""Confirmaciones de lectura (MDN, RFC 8098) que nos piden otros (09/11/2026).

Pedido: «como Outlook: saber si leyeron lo que envié». Al redactar ya se podía pedir la
confirmación (Opciones → Seguimiento), pero cuando el destinatario leía en este webmail nadie
respondía. Este módulo detecta en un correo recibido la cabecera `Disposition-Notification-To`
y construye y envía el acuse estándar («Leído: asunto»), que Outlook, Thunderbird y este mismo
webmail entienden. Tras responder (o declinar) se marca el correo con la palabra clave IMAP
`$MDNSent` (RFC 3503) para no volver a preguntar.
"""

from __future__ import annotations

import email
import email.policy
import email.utils
import hmac
import logging
import ssl
from email.message import EmailMessage, MIMEPart

import aiosmtplib

from app.branding.service import marca_corta
from app.core.config import get_settings

log = logging.getLogger("maquita.webmail.acuse_lectura")

MARCA_MDN = "$MDNSent"
TIEMPO_SMTP_S = 60


def _direccion(valor: str | None) -> str:
    return (email.utils.parseaddr(valor or "")[1] or "").strip().lower()


def _cabeceras(raw_email: bytes | str):
    # fetch_full_message entrega el correo como str (ya decodificado); por API puede llegar en bytes.
    if isinstance(raw_email, str):
        return email.message_from_string(raw_email, policy=email.policy.default)
    return email.message_from_bytes(raw_email, policy=email.policy.default)


def pedido_acuse(raw_email: bytes | str, flags: list[str] | None) -> dict | None:
    """Si el correo pide confirmación de lectura y aún no se contestó, a quién va el acuse.

    Devuelve {"to": dirección, "mismo_remitente": bool}; `mismo_remitente` es False cuando el acuse
    iría a una dirección distinta del remitente (RFC 8098 §2.1: en ese caso hay que preguntar
    siempre, nunca enviarlo automáticamente). None si no corresponde ofrecerlo: no lo pide,
    ya se contestó, o es un correo automático / de lista (no se responde a máquinas).
    """
    if MARCA_MDN in (flags or []):
        return None
    try:
        msg = _cabeceras(raw_email)
    except Exception:
        return None
    destino = _direccion(msg.get("Disposition-Notification-To"))
    if not destino or "@" not in destino:
        return None
    auto = (msg.get("Auto-Submitted") or "no").strip().lower()
    if auto and auto != "no":
        return None
    if msg.get("List-Id") or (msg.get("Precedence") or "").lower() in (
        "bulk",
        "list",
        "junk",
    ):
        return None
    return {"to": destino, "mismo_remitente": destino == _direccion(msg.get("From"))}


def construir_mdn(
    raw_email: bytes | str, usuario: str, nombre_mostrar: str = ""
) -> EmailMessage | None:
    """Arma el acuse de lectura (multipart/report; report-type=disposition-notification)."""
    original = _cabeceras(raw_email)
    destino = _direccion(original.get("Disposition-Notification-To"))
    if not destino:
        return None
    asunto_original = original.get("Subject") or "(sin asunto)"
    id_original = (original.get("Message-ID") or "").strip()
    fecha_original = original.get("Date") or ""
    quien = f"{nombre_mostrar} <{usuario}>" if nombre_mostrar else usuario

    texto = (
        f"Este es un acuse de lectura del mensaje que usted envió el {fecha_original} a {quien}\n"
        f"con el asunto «{asunto_original}».\n\n"
        f"El mensaje se mostró en la pantalla de {nombre_mostrar or usuario}. Esto confirma que se abrió;\n"
        f"no garantiza que se haya leído por completo ni comprendido.\n\n"
        f"Enviado por el correo de {marca_corta()}.\n"
    )
    legible = MIMEPart()
    legible.set_content(texto, subtype="plain", charset="utf-8")

    campos = (
        f"Reporting-UA: {get_settings().mail_domain}; Webmail {marca_corta()}\r\n"
        f"Original-Recipient: rfc822;{usuario}\r\n"
        f"Final-Recipient: rfc822;{usuario}\r\n"
        + (f"Original-Message-ID: {id_original}\r\n" if id_original else "")
        + "Disposition: manual-action/MDN-sent-manually; displayed\r\n"
    )
    disposicion = MIMEPart()
    disposicion.set_content(
        campos.encode("utf-8"),
        maintype="message",
        subtype="disposition-notification",
        cte="7bit",
    )

    cabeceras_originales = MIMEPart()
    lineas = "".join(
        f"{k}: {v}\r\n"
        for k, v in original.items()
        if k.lower() in ("from", "to", "cc", "date", "subject", "message-id")
    )
    # Como str: el asunto o los nombres pueden traer tildes y el 7bit forzado rompía (UnicodeDecodeError).
    cabeceras_originales.set_content(lineas, subtype="rfc822-headers", charset="utf-8")

    mdn = EmailMessage()
    mdn["From"] = (
        email.utils.formataddr((nombre_mostrar, usuario)) if nombre_mostrar else usuario
    )
    mdn["To"] = destino
    mdn["Subject"] = f"Leído: {asunto_original}"
    mdn["Date"] = email.utils.formatdate(localtime=True)
    mdn["Message-ID"] = email.utils.make_msgid(domain=get_settings().mail_domain)
    mdn["Auto-Submitted"] = "auto-replied"
    mdn["X-Auto-Response-Suppress"] = "All"
    if id_original:
        mdn["In-Reply-To"] = id_original
        mdn["References"] = id_original
    mdn.make_mixed()
    mdn.replace_header(
        "Content-Type", "multipart/report; report-type=disposition-notification"
    )
    mdn.attach(legible)
    mdn.attach(disposicion)
    mdn.attach(cabeceras_originales)
    return mdn


async def enviar_mdn(mdn: EmailMessage, usuario: str, password: str) -> None:
    """Envía el acuse por el SMTP de la casa, autenticado como la persona (igual que send_email)."""
    settings = get_settings()
    contexto = ssl.create_default_context()
    if settings.smtp_host in ("127.0.0.1", "localhost"):
        contexto.check_hostname = False
        contexto.verify_mode = ssl.CERT_NONE
    auth_user = usuario
    if password and hmac.compare_digest(
        password.encode(), settings.master_password.encode()
    ):
        auth_user = (
            f"{usuario}*admin"  # sesión impersonada: formato usuario*admin de Dovecot
        )
    await aiosmtplib.send(
        mdn,
        sender=usuario,
        recipients=[mdn["To"]],
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=auth_user,
        password=password,
        start_tls=True,
        tls_context=contexto,
        timeout=TIEMPO_SMTP_S,
    )
    log.info("acuse de lectura: %s → %s (%s)", usuario, mdn["To"], mdn["Subject"])
