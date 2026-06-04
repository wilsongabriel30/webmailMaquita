import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr, formatdate, make_msgid, parseaddr
from typing import Optional

from app.config import get_settings


async def send_email(
    username: str,
    password: str,
    to: list[str],
    subject: str,
    html_body: str = "",
    text_body: str = "",
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    in_reply_to: str = "",
    references: str = "",
    attachments: list[dict] | None = None,
) -> dict:
    """Send an email via SMTP (authenticated as the user)."""
    settings = get_settings()

    msg = MIMEMultipart("mixed")
    msg["From"] = username
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=settings.mail_domain)

    if cc:
        msg["Cc"] = ", ".join(cc)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    # Body
    body_part = MIMEMultipart("alternative")
    if text_body:
        body_part.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        body_part.attach(MIMEText(html_body, "html", "utf-8"))
    elif text_body:
        pass  # already attached
    else:
        body_part.attach(MIMEText("", "plain", "utf-8"))

    msg.attach(body_part)

    # Attachments
    if attachments:
        for att in attachments:
            part = MIMEBase(att.get("content_type", "application/octet-stream").split("/")[0],
                           att.get("content_type", "application/octet-stream").split("/")[-1])
            part.set_payload(att["data"])
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=att["filename"])
            msg.attach(part)

    all_recipients = list(to)
    if cc:
        all_recipients.extend(cc)
    if bcc:
        all_recipients.extend(bcc)

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=parseaddr(username)[1] or username,
        password=password,
        start_tls=True,
        recipients=all_recipients,
    )

    return {"message_id": msg["Message-ID"], "status": "sent"}
