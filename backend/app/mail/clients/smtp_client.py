"""Pure SMTP client — handles email sending only.

Supports text+HTML multipart, file attachments, inline CID images.

╔══════════════════════════════════════════════════════════════════════╗
║  CRITICAL: NO MODIFICAR SIN CORRER LOS TESTS DE ENTREGABILIDAD    ║
║                                                                      ║
║  Este módulo construye los correos MIME que salen al mundo.          ║
║  Cualquier cambio incorrecto ENVÍA CORREOS A SPAM.                   ║
║                                                                      ║
║  Auditoría: 14-Abril-2026 — Score 10/10 en mail-tester.com          ║
║  Reglas que NO se deben romper:                                      ║
║    1. Siempre generar text/plain real (nunca vacío)                  ║
║    2. Siempre envolver HTML en DOCTYPE + <html> + <body>             ║
║    3. NUNCA agregar X-Priority, X-MSMail-Priority, Importance        ║
║    4. Content-Type DEBE ser multipart/alternative o multipart/mixed  ║
║    5. Charset DEBE ser utf-8                                         ║
║                                                                      ║
║  Antes de modificar, ejecutar:                                       ║
║    python3 backend/tests/test_mime_deliverability.py                 ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import re as _re
from dataclasses import dataclass, field
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, parseaddr

import aiosmtplib

from app.branding.service import app_name_cacheado, org_name_cacheado
from app.config import get_settings

# ─── Headers que NUNCA deben estar en un correo saliente ───
# Agregar cualquiera de estos sube el score de SpamAssassin y envía a spam.
_FORBIDDEN_HEADERS = frozenset(
    {
        "X-Priority",
        "X-MSMail-Priority",
        "Importance",
        "X-MimeOLE",
        "X-Mailer-Version",
    }
)


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text for multipart/alternative.

    CRITICAL: Esta función DEBE retornar texto real, nunca string vacío
    cuando se le pasa HTML con contenido. Si retorna vacío, SpamAssassin
    penaliza con MPART_ALT_DIFF y MIME_HTML_ONLY (+0.1 a +1.1 puntos).
    """
    text = _re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", html)
    text = _re.sub(r"<[^>]+>", "", text)
    text = _re.sub(r"&nbsp;", " ", text)
    text = _re.sub(r"&amp;", "&", text)
    text = _re.sub(r"&lt;", "<", text)
    text = _re.sub(r"&gt;", ">", text)
    text = _re.sub(r"&quot;", '"', text)
    text = _re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _wrap_html(html: str) -> str:
    """Ensure HTML has proper document structure.

    CRITICAL: Sin DOCTYPE + <html> + <body>, SpamAssassin penaliza con
    HTML_MIME_NO_HTML_TAG (+0.377 puntos). Gmail y Outlook también
    pueden renderizar mal el correo.
    """
    stripped = html.strip()
    if stripped.lower().startswith("<!doctype") or stripped.lower().startswith("<html"):
        return stripped
    return (
        "<!DOCTYPE html>\n"
        '<html lang="es">\n'
        '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>\n'
        '<body style="font-family: Calibri, Arial, sans-serif; font-size: 14px; color: #333;">\n'
        f"{stripped}\n"
        "</body>\n"
        "</html>"
    )


@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    is_inline: bool = False
    cid: str = ""


@dataclass
class OutgoingEmail:
    from_addr: str
    to: list[str]
    subject: str
    text_body: str = ""
    html_body: str = ""
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    in_reply_to: str = ""
    references: str = ""
    attachments: list[EmailAttachment] = field(default_factory=list)
    request_read_receipt: bool = False
    request_delivery_receipt: bool = False


def build_mime_message(email_data: OutgoingEmail) -> MIMEMultipart:
    """Build a MIME message optimized for maximum deliverability.

    INVARIANTES (no romper):
    - Siempre multipart/alternative (o mixed si hay adjuntos)
    - Siempre text/plain + text/html (text/plain NUNCA vacío si hay HTML)
    - HTML siempre con DOCTYPE + <html> + <body>
    - Sin headers prohibidos (_FORBIDDEN_HEADERS)
    """
    settings = get_settings()
    has_attachments = any(not a.is_inline for a in email_data.attachments)
    has_inline = any(a.is_inline for a in email_data.attachments)

    msg = MIMEMultipart("mixed") if has_attachments else MIMEMultipart("alternative")

    # ─── Headers estándar (SOLO estos, no agregar más sin verificar spam score) ───
    msg["From"] = email_data.from_addr
    msg["To"] = ", ".join(email_data.to)
    msg["Subject"] = email_data.subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=settings.mail_domain)
    # Marca: este punto no tiene la base a mano, asi que se lee de la cache de
    # proceso. Si aun no esta rellena se usan los valores por defecto: un correo
    # nunca debe dejar de salir por consultar el nombre de la organizacion.
    msg["X-Mailer"] = f"{app_name_cacheado()}/1.0"
    msg["Organization"] = org_name_cacheado()

    if email_data.cc:
        msg["Cc"] = ", ".join(email_data.cc)
    if email_data.in_reply_to:
        msg["In-Reply-To"] = email_data.in_reply_to
    if email_data.references:
        msg["References"] = email_data.references

    if email_data.request_read_receipt:
        msg["Disposition-Notification-To"] = email_data.from_addr
    if email_data.request_delivery_receipt:
        msg["Return-Receipt-To"] = email_data.from_addr

    body_part = MIMEMultipart("alternative") if has_attachments else msg

    # ─── REGLA 1: text/plain SIEMPRE real (nunca vacío si hay HTML) ───
    text_body = email_data.text_body or (
        _html_to_text(email_data.html_body) if email_data.html_body else ""
    )
    if text_body:
        body_part.attach(MIMEText(text_body, "plain", "utf-8"))

    # ─── REGLA 2: HTML siempre con estructura DOCTYPE completa ───
    if email_data.html_body:
        wrapped_html = _wrap_html(email_data.html_body)
        if has_inline:
            related = MIMEMultipart("related")
            related.attach(MIMEText(wrapped_html, "html", "utf-8"))
            for att in email_data.attachments:
                if att.is_inline and att.cid:
                    img_part = _build_attachment_part(att)
                    img_part.add_header("Content-ID", f"<{att.cid}>")
                    related.attach(img_part)
            body_part.attach(related)
        else:
            body_part.attach(MIMEText(wrapped_html, "html", "utf-8"))
    elif not text_body:
        body_part.attach(MIMEText("", "plain", "utf-8"))

    if has_attachments and body_part is not msg:
        msg.attach(body_part)

    for att in email_data.attachments:
        if not att.is_inline:
            part = _build_attachment_part(att)
            part.add_header("Content-Disposition", "attachment", filename=att.filename)
            msg.attach(part)

    # ─── REGLA 3: Validación final — rechazar headers prohibidos ───
    _assert_no_forbidden_headers(msg)

    return msg


def _assert_no_forbidden_headers(msg: MIMEMultipart) -> None:
    """Safety check: asegurar que no se colaron headers que causan spam.

    Si alguien agrega un header prohibido por error, este check lo detecta
    ANTES de que el correo salga. Falla ruidosamente para que se note.
    """
    for header_name in _FORBIDDEN_HEADERS:
        if msg.get(header_name):
            raise ValueError(
                f"HEADER PROHIBIDO detectado: '{header_name}'. "
                f"Este header causa que los correos vayan a spam. "
                f"Ver documentación en 09-AUDITORIA-ENTREGABILIDAD-20260414.md"
            )


def _build_attachment_part(att: EmailAttachment) -> MIMEBase:
    maintype, subtype = (
        att.content_type.split("/", 1)
        if "/" in att.content_type
        else ("application", "octet-stream")
    )
    if maintype == "image":
        part = MIMEImage(att.content, _subtype=subtype)
    else:
        part = MIMEBase(maintype, subtype)
        part.set_payload(att.content)
        encoders.encode_base64(part)
    return part


async def send_email(email_data: OutgoingEmail, password: str) -> dict:
    settings = get_settings()
    msg = build_mime_message(email_data)
    all_recipients = list(email_data.to) + email_data.cc + email_data.bcc

    import ssl

    tls_context = ssl.create_default_context()
    if settings.smtp_host in ("127.0.0.1", "localhost"):
        tls_context.check_hostname = False
        tls_context.verify_mode = ssl.CERT_NONE

    # En sesión impersonada (admin abre el buzón de un usuario) el password es el
    # master de Dovecot, que exige el formato usuario*admin para el SASL SMTP
    # (igual que el login IMAP). Si no, Dovecot responde 535 auth failed.
    auth_user = parseaddr(email_data.from_addr)[1] or email_data.from_addr
    if password and password == settings.master_password:
        auth_user = f"{auth_user}*admin"

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=auth_user,
        password=password,
        start_tls=True,
        tls_context=tls_context,
        recipients=all_recipients,
    )

    return {
        "message_id": msg["Message-ID"],
        "status": "sent",
        "raw_message": msg.as_string(),
    }


def build_draft_message(email_data: OutgoingEmail) -> str:
    """Build MIME message for saving as draft. Returns raw string."""
    return build_mime_message(email_data).as_string()
