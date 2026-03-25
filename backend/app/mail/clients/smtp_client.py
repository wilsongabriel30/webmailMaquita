"""Pure SMTP client — handles email sending only.

Supports text+HTML multipart, file attachments, inline CID images.
"""
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
from email.utils import formatdate, make_msgid
from dataclasses import dataclass, field

from app.core.config import get_settings


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
    settings = get_settings()
    has_attachments = any(not a.is_inline for a in email_data.attachments)
    has_inline = any(a.is_inline for a in email_data.attachments)

    msg = MIMEMultipart("mixed") if has_attachments else MIMEMultipart("alternative")

    msg["From"] = email_data.from_addr
    msg["To"] = ", ".join(email_data.to)
    msg["Subject"] = email_data.subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=settings.mail_domain)
    msg["X-Mailer"] = "Maquita Webmail 0.3.0"

    if email_data.cc:
        msg["Cc"] = ", ".join(email_data.cc)
    if email_data.in_reply_to:
        msg["In-Reply-To"] = email_data.in_reply_to
    if email_data.references:
        msg["References"] = email_data.references

    # Read / delivery receipt headers
    if email_data.request_read_receipt:
        msg["Disposition-Notification-To"] = email_data.from_addr
    if email_data.request_delivery_receipt:
        msg["Return-Receipt-To"] = email_data.from_addr

    body_part = MIMEMultipart("alternative") if has_attachments else msg

    if email_data.text_body:
        body_part.attach(MIMEText(email_data.text_body, "plain", "utf-8"))

    if email_data.html_body:
        if has_inline:
            related = MIMEMultipart("related")
            related.attach(MIMEText(email_data.html_body, "html", "utf-8"))
            for att in email_data.attachments:
                if att.is_inline and att.cid:
                    img_part = _build_attachment_part(att)
                    img_part.add_header("Content-ID", f"<{att.cid}>")
                    related.attach(img_part)
            body_part.attach(related)
        else:
            body_part.attach(MIMEText(email_data.html_body, "html", "utf-8"))
    elif not email_data.text_body:
        body_part.attach(MIMEText("", "plain", "utf-8"))

    if has_attachments and body_part is not msg:
        msg.attach(body_part)

    for att in email_data.attachments:
        if not att.is_inline:
            part = _build_attachment_part(att)
            part.add_header("Content-Disposition", "attachment", filename=att.filename)
            msg.attach(part)

    return msg


def _build_attachment_part(att: EmailAttachment) -> MIMEBase:
    maintype, subtype = att.content_type.split("/", 1) if "/" in att.content_type else ("application", "octet-stream")
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
    # Local SMTP: skip cert verification (cert is for mail.example.org, not 127.0.0.1)
    if settings.smtp_host in ("127.0.0.1", "localhost"):
        tls_context.check_hostname = False
        tls_context.verify_mode = ssl.CERT_NONE

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=email_data.from_addr,
        password=password,
        start_tls=True,
        tls_context=tls_context,
        recipients=all_recipients,
    )

    return {"message_id": msg["Message-ID"], "status": "sent", "raw_message": msg.as_string()}


def build_draft_message(email_data: OutgoingEmail) -> str:
    """Build MIME message for saving as draft. Returns raw string."""
    return build_mime_message(email_data).as_string()
