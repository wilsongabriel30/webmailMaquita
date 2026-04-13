"""Send service — orchestrates sending email with attachments."""
import re
from app.mail.clients.smtp_client import send_email as smtp_send, OutgoingEmail, EmailAttachment
from app.mail.clients.imap_client import append_message


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text for the text/plain MIME part."""
    if not html:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</h[1-6]>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"&[a-z]+;", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def _get_disclaimer(db, domain: str) -> tuple[str, str] | None:
    """Get active corporate disclaimer for domain."""
    try:
        row = await db.fetchrow(
            "SELECT html_footer, text_footer FROM corporate_disclaimer WHERE domain = $1 AND is_active = TRUE",
            domain
        )
        if row and (row["html_footer"] or row["text_footer"]):
            return row["html_footer"], row["text_footer"]
    except Exception:
        pass
    return None


async def send_and_save(
    imap,
    password: str,
    from_addr: str,
    to: list[str],
    subject: str,
    text_body: str = "",
    html_body: str = "",
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    in_reply_to: str = "",
    references: str = "",
    attachments: list[dict] | None = None,
    sent_folder: str = "Sent",
    draft_uid: int | None = None,
    display_name: str = "",
    db = None,
    request_read_receipt: bool = False,
    request_delivery_receipt: bool = False,
) -> dict:
    """Send email via SMTP and save copy to Sent folder."""
    # Format From with display name if available
    if display_name:
        from_formatted = f"{display_name} <{from_addr}>"
    else:
        from_formatted = from_addr

    # Build attachment list
    email_attachments = []
    if attachments:
        for att in attachments:
            email_attachments.append(EmailAttachment(
                filename=att["filename"],
                content=att["content"],
                content_type=att.get("content_type", "application/octet-stream"),
                is_inline=att.get("is_inline", False),
                cid=att.get("cid", ""),
            ))

    # Auto-generate text_body from html_body if empty
    if not text_body and html_body:
        text_body = _html_to_text(html_body)

    # Inject corporate disclaimer if configured
    if db:
        _domain = from_addr.split('@')[1] if '@' in from_addr else ''
        _disc = await _get_disclaimer(db, _domain)
        if _disc:
            _dh, _dt = _disc
            if _dh and html_body:
                html_body = html_body + '<div style="margin-top:16px;padding-top:12px;border-top:1px solid #edebe9;font-size:11px;color:#605e5c;">' + _dh + '</div>'
            if _dt and text_body:
                text_body = text_body + chr(10) + chr(10) + '---' + chr(10) + _dt

    email_data = OutgoingEmail(
        from_addr=from_formatted,
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        cc=cc or [],
        bcc=bcc or [],
        in_reply_to=in_reply_to,
        references=references,
        attachments=email_attachments,
        request_read_receipt=request_read_receipt,
        request_delivery_receipt=request_delivery_receipt,
    )

    # Send
    result = await smtp_send(email_data, password)

    # Save to Sent folder
    if result.get("raw_message"):
        await append_message(imap, sent_folder, result["raw_message"], "\\Seen")

    # Delete draft if applicable
    if draft_uid:
        from app.mail.clients.imap_client import uid_delete_message
        await uid_delete_message(imap, "Drafts", draft_uid)

    return {"message_id": result["message_id"], "status": "sent"}
