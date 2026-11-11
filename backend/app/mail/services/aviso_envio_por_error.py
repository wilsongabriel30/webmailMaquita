"""Aviso de «enviado por error» a destinatarios externos (11/11/2026).

De un buzón ajeno no se puede retirar nada. Lo que sí se puede es dejar constancia: se responde
en la MISMA conversación (mismo asunto, `In-Reply-To` y `References` al correo original) diciendo
que el mensaje se envió por error y que no se tenga en cuenta su contenido. El remitente recibe
copia oculta: le queda la constancia en su buzón, dentro del hilo.
"""

from __future__ import annotations

import html
import subprocess
from datetime import datetime
from email.header import decode_header, make_header

from app.mail.clients.smtp_client import OutgoingEmail

MAQUITA_SUDO = "/usr/local/sbin/maquita-sudo"
SIN_ASUNTO = "(Sin asunto)"


def decodificar_asunto(crudo: str | None) -> str:
    """Asunto legible a partir de la cabecera tal como la devuelve doveadm (RFC 2047, plegada)."""
    texto = " ".join((crudo or "").split())
    if not texto:
        return ""
    try:
        return str(make_header(decode_header(texto))).strip()
    except Exception:
        return texto


def asunto_en_enviados(username: str, message_id: str) -> str:
    """Asunto del correo original en «Enviados» del remitente («» si no se puede leer)."""
    try:
        result = subprocess.run(
            [
                "sudo",
                "-n",
                MAQUITA_SUDO,
                "doveadm",
                "fetch",
                "-u",
                username,
                "hdr.subject",
                "mailbox",
                "Sent",
                "header",
                "message-id",
                message_id,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return ""
        primera = result.stdout.split("\f")[0]
        if "hdr.subject:" not in primera:
            return ""
        return decodificar_asunto(primera.split("hdr.subject:", 1)[1])
    except Exception:
        return ""


def asunto_respuesta(asunto: str) -> str:
    """«RE: asunto», sin duplicar el prefijo si ya lo trae."""
    asunto = (asunto or "").strip() or SIN_ASUNTO
    if asunto[:3].lower() == "re:":
        return asunto
    return f"RE: {asunto}"


def construir(
    remitente: str,
    destinatario: str,
    message_id: str,
    asunto: str,
    enviado: datetime | None,
    marca: str,
) -> OutgoingEmail:
    """El correo de aviso, como respuesta dentro de la conversación original."""
    asunto = (asunto or "").strip() or SIN_ASUNTO
    cuando = f" el {enviado:%d/%m/%Y} a las {enviado:%H:%M}" if enviado else ""
    texto = (
        f"El mensaje anterior, «{asunto}», enviado{cuando} desde {remitente}, se envió por error.\n\n"
        "Le pedimos no tener en cuenta su contenido ni sus adjuntos, no reenviarlo y eliminarlo. "
        "Si corresponde, recibirá un mensaje corregido.\n\n"
        "Disculpe las molestias.\n\n"
        f"Aviso automático del correo de {marca}, enviado a solicitud de {remitente}."
    )
    cuerpo = f"""<div style="font-family:Calibri,Segoe UI,sans-serif;max-width:600px;color:#323130">
<div style="background:#fff4ce;border:1px solid #f8d22a;border-radius:4px;padding:12px 16px;margin-bottom:14px">
<b>Mensaje enviado por error</b></div>
<p>El mensaje anterior, «{html.escape(asunto)}», enviado{cuando} desde {html.escape(remitente)},
<b>se envió por error</b>.</p>
<p>Le pedimos no tener en cuenta su contenido ni sus adjuntos, no reenviarlo y eliminarlo.
Si corresponde, recibirá un mensaje corregido.</p>
<p>Disculpe las molestias.</p>
<p style="font-size:11px;color:#8a8886;border-top:1px solid #edebe9;padding-top:10px">
Aviso automático del correo de {html.escape(marca)}, enviado a solicitud de {html.escape(remitente)}.</p>
</div>"""
    return OutgoingEmail(
        from_addr=remitente,
        to=[destinatario],
        bcc=[remitente],
        subject=asunto_respuesta(asunto),
        html_body=cuerpo,
        text_body=texto,
        in_reply_to=message_id,
        references=message_id,
    )
