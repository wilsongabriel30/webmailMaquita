"""Compose router — send, drafts, upload attachments, schedule."""
import base64
import re
import nh3
from fastapi import APIRouter, Request, Depends, UploadFile, File, Form, HTTPException
from typing import Optional
import json

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password, get_imap_login_user
from app.mail.clients.imap_client import get_imap_connection
from app.mail.services.send_service import send_and_save
from app.mail.services.draft_service import save_draft, delete_draft
from app.mail.clients.smtp_client import OutgoingEmail
from app.mail.schemas.messages import ComposeRequest, DraftRequest, ScheduleRequest
from app.security.account_protection import check_send_anomaly
from app.mail.services.large_attachments import SIZE_THRESHOLD, upload_and_share, format_link_html

async def _save_sent_recipients(db, sender: str, recipients: list[str]):
    """Auto-save recipients to sent_recipients for future autocomplete."""
    for email in recipients:
        if not email or not email.strip():
            continue
        email = email.strip().lower()
        # Extract name from "Name <email>" format
        name = ""
        if "<" in email:
            import re
            m = re.match(r'^"?([^"<]+)"?\s*<([^>]+)>', email)
            if m:
                name = m.group(1).strip()
                email = m.group(2).strip()
        try:
            await db.execute("""
                INSERT INTO sent_recipients (sender, recipient_email, recipient_name, last_sent_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (sender, recipient_email)
                DO UPDATE SET last_sent_at = NOW(),
                    recipient_name = CASE WHEN $3 != '' THEN $3 ELSE sent_recipients.recipient_name END
            """, sender, email, name)
        except Exception:
            pass




async def _check_send_rate(request, username: str):
    """Rate limit email sending: 10/min, 50/hour per user."""
    redis = request.app.state.redis
    # Per-minute
    min_key = f"send_rl:min:{username}"
    min_count = await redis.incr(min_key)
    if min_count == 1:
        await redis.expire(min_key, 60)
    if min_count > 5:
        raise HTTPException(status_code=429, detail="Límite de envío: máximo 5 correos por minuto")

    # Per-hour
    hour_key = f"send_rl:hour:{username}"
    hour_count = await redis.incr(hour_key)
    if hour_count == 1:
        await redis.expire(hour_key, 3600)
    if hour_count > 30:
        raise HTTPException(status_code=429, detail="Límite de envío: máximo 30 correos por hora")

    # Per-day
    day_key = f"send_rl:day:{username}"
    day_count = await redis.incr(day_key)
    if day_count == 1:
        await redis.expire(day_key, 86400)
    if day_count > 200:
        raise HTTPException(status_code=429, detail="Límite de envío: máximo 200 correos por día")

router = APIRouter(prefix="/api/mail", tags=["mail-compose"])


@router.post("/send")
async def send(
    request: Request,
    body: ComposeRequest,
    username: str = Depends(get_current_user),
):
    password = await get_user_password(request, username)
    await _check_send_rate(request, username)

    # ── Detección de envío masivo anómalo (protección anti-compromiso) ──
    all_rcpts = list(body.to or []) + list(body.cc or []) + list(body.bcc or [])
    anomaly = await check_send_anomaly(request.app.state.redis, username, all_rcpts)
    if not anomaly["allowed"]:
        raise HTTPException(status_code=429, detail=anomaly["reason"])

    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        # Get display name from user preferences
        db = request.app.state.db_pool
        display_name = ""
        row = await db.fetchrow(
            "SELECT display_name FROM user_preferences WHERE username = $1", username
        )
        if row and row["display_name"]:
            display_name = row["display_name"]

        # Decode base64 attachments — large files go to Nextcloud
        attachments = []
        large_links_html = []
        if body.attachments:
            for att in body.attachments:
                try:
                    content = base64.b64decode(att.content_b64)
                except Exception:
                    content = b""
                if len(content) >= SIZE_THRESHOLD and not (att.is_inline or False):
                    # Upload to Nextcloud and get share link
                    share_url = await upload_and_share(username, password, att.filename, content)
                    if share_url:
                        large_links_html.append(format_link_html(att.filename, len(content), share_url))
                        continue  # skip inline attachment
                attachments.append({
                    "filename": att.filename,
                    "content": content,
                    "content_type": att.content_type or "application/octet-stream",
                    "is_inline": att.is_inline or False,
                    "cid": att.cid or "",
                })
        # Append Nextcloud links to HTML body
        if large_links_html:
            links_block = "<br>".join(large_links_html)
            body.html_body = (body.html_body or "") + "<br>" + links_block
        result = await send_and_save(
            imap=imap,
            password=password,
            from_addr=username,
            to=body.to,
            subject=body.subject,
            text_body=body.text_body,
            html_body=body.html_body,
            cc=body.cc,
            bcc=body.bcc,
            in_reply_to=body.in_reply_to,
            references=body.references,
            draft_uid=body.draft_uid,
            display_name=display_name,
            db=db,
            attachments=attachments,
            request_read_receipt=body.request_read_receipt,
            request_delivery_receipt=body.request_delivery_receipt,
        )

        # Auto-save all recipients for future autocomplete
        all_recipients = list(body.to or [])
        if body.cc:
            all_recipients.extend(body.cc)
        if body.bcc:
            all_recipients.extend(body.bcc)
        await _save_sent_recipients(db, username, all_recipients)

        return result
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.post("/send-multipart")
async def send_multipart(
    request: Request,
    to: str = Form(...),
    subject: str = Form(""),
    html_body: str = Form(""),
    text_body: str = Form(""),
    cc: str = Form(""),
    bcc: str = Form(""),
    in_reply_to: str = Form(""),
    references: str = Form(""),
    draft_uid: Optional[int] = Form(None),
    files: list[UploadFile] = File(default=[]),
    username: str = Depends(get_current_user),
):
    """Alternative multipart/form-data endpoint for large attachments."""
    password = await get_user_password(request, username)
    await _check_send_rate(request, username)

    # ── Detección de envío masivo anómalo (protección anti-compromiso) ──
    all_rcpts = list(body.to or []) + list(body.cc or []) + list(body.bcc or [])
    anomaly = await check_send_anomaly(request.app.state.redis, username, all_rcpts)
    if not anomaly["allowed"]:
        raise HTTPException(status_code=429, detail=anomaly["reason"])

    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        db = request.app.state.db_pool
        display_name = ""
        row = await db.fetchrow(
            "SELECT display_name FROM user_preferences WHERE username = $1", username
        )
        if row and row["display_name"]:
            display_name = row["display_name"]

        attachments = []
        for f in files:
            content = await f.read()
            attachments.append({
                "filename": f.filename or "attachment",
                "content": content,
                "content_type": f.content_type or "application/octet-stream",
                "is_inline": False,
                "cid": "",
            })

        to_list = [s.strip() for s in to.split(",") if s.strip()]
        cc_list = [s.strip() for s in cc.split(",") if s.strip()] if cc else []
        bcc_list = [s.strip() for s in bcc.split(",") if s.strip()] if bcc else []

        result = await send_and_save(
            imap=imap,
            password=password,
            from_addr=username,
            to=to_list,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            cc=cc_list,
            bcc=bcc_list,
            in_reply_to=in_reply_to,
            references=references,
            draft_uid=draft_uid,
            display_name=display_name,
            attachments=attachments,
        )

        # Auto-save all recipients for future autocomplete
        all_recipients = to_list + cc_list + bcc_list
        await _save_sent_recipients(db, username, all_recipients)

        return result
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.post("/drafts")
async def create_draft(
    request: Request,
    body: DraftRequest,
    username: str = Depends(get_current_user),
):
    password = await get_user_password(request, username)
    await _check_send_rate(request, username)

    # ── Detección de envío masivo anómalo (protección anti-compromiso) ──
    all_rcpts = list(body.to or []) + list(body.cc or []) + list(body.bcc or [])
    anomaly = await check_send_anomaly(request.app.state.redis, username, all_rcpts)
    if not anomaly["allowed"]:
        raise HTTPException(status_code=429, detail=anomaly["reason"])

    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        email_data = OutgoingEmail(
            from_addr=username,
            to=body.to,
            subject=body.subject,
            text_body=body.text_body,
            html_body=body.html_body,
            cc=body.cc or [],
            bcc=body.bcc or [],
            in_reply_to=body.in_reply_to,
            references=body.references,
        )
        new_uid = await save_draft(imap, email_data, body.existing_draft_uid)
        return {"status": "saved", "draft_uid": new_uid}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.delete("/drafts/{uid}")
async def remove_draft(
    uid: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    password = await get_user_password(request, username)
    await _check_send_rate(request, username)

    # ── Detección de envío masivo anómalo (protección anti-compromiso) ──
    all_rcpts = list(body.to or []) + list(body.cc or []) + list(body.bcc or [])
    anomaly = await check_send_anomaly(request.app.state.redis, username, all_rcpts)
    if not anomaly["allowed"]:
        raise HTTPException(status_code=429, detail=anomaly["reason"])

    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        ok = await delete_draft(imap, uid)
        if not ok:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Failed to delete draft")
        return {"status": "deleted"}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


# -- Scheduled emails ----------------------------------------------------------

async def _ensure_scheduled_table(db):
    # Tabla creada por migrations/init_tables.sql (Fase 3)
    # scheduled_emails
    pass


@router.post("/schedule")
async def schedule_send(
    request: Request,
    body: ScheduleRequest,
    username: str = Depends(get_current_user),
):
    """Schedule an email for future sending."""
    db = request.app.state.db_pool
    await _ensure_scheduled_table(db)

    row = await db.fetchrow("""
        INSERT INTO scheduled_emails
            (username, to_list, cc_list, bcc_list, subject, html_body, text_body,
             in_reply_to, "references", scheduled_at, status,
             request_read_receipt, request_delivery_receipt)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::timestamptz, 'pending', $11, $12)
        RETURNING id, scheduled_at
    """,
        username,
        json.dumps(body.to),
        json.dumps(body.cc or []),
        json.dumps(body.bcc or []),
        body.subject,
        body.html_body,
        body.text_body or "",
        body.in_reply_to or "",
        body.references or "",
        body.scheduled_at,
        body.request_read_receipt,
        body.request_delivery_receipt,
    )

    return {
        "status": "scheduled",
        "id": row["id"],
        "scheduled_at": str(row["scheduled_at"]),
    }


@router.get("/scheduled")
async def list_scheduled(
    request: Request,
    username: str = Depends(get_current_user),
):
    """List pending scheduled emails for current user."""
    db = request.app.state.db_pool
    await _ensure_scheduled_table(db)

    rows = await db.fetch("""
        SELECT id, to_list, cc_list, bcc_list, subject, scheduled_at, status, created_at
        FROM scheduled_emails
        WHERE username = $1 AND status = 'pending'
        ORDER BY scheduled_at ASC
    """, username)

    return [
        {
            "id": r["id"],
            "to": json.loads(r["to_list"]) if isinstance(r["to_list"], str) else r["to_list"],
            "cc": json.loads(r["cc_list"]) if isinstance(r["cc_list"], str) else r["cc_list"],
            "bcc": json.loads(r["bcc_list"]) if isinstance(r["bcc_list"], str) else r["bcc_list"],
            "subject": r["subject"],
            "scheduled_at": str(r["scheduled_at"]),
            "status": r["status"],
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]


@router.delete("/scheduled/{email_id}")
async def cancel_scheduled(
    email_id: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Cancel a scheduled email."""
    db = request.app.state.db_pool
    await _ensure_scheduled_table(db)

    result = await db.execute("""
        UPDATE scheduled_emails SET status = 'cancelled'
        WHERE id = $1 AND username = $2 AND status = 'pending'
    """, email_id, username)

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Scheduled email not found or already sent")

    return {"status": "cancelled", "id": email_id}


# -- Email Templates -----------------------------------------------------------

from pydantic import BaseModel, field_validator

class TemplateCreate(BaseModel):
    name: str
    subject: str = ""
    html_body: str = ""
    category: str = ""

    @field_validator("subject", mode="before")
    @classmethod
    def strip_html_subject(cls, v):
        # Strip ALL HTML from subject
        return re.sub(r"<[^>]+>", "", v).strip() if v else ""

    @field_validator("html_body", mode="before")
    @classmethod
    def sanitize_body(cls, v):
        if not v:
            return ""
        return nh3.clean(
            v,
            tags={"p","br","strong","em","u","s","a","ul","ol","li",
                  "h1","h2","h3","h4","blockquote","img","table","tr",
                  "td","th","thead","tbody","span","div","sub","sup","hr"},
            attributes={
                "a": {"href","title","target"},
                "img": {"src","alt","width","height"},
                "td": {"colspan","rowspan"},
                "th": {"colspan","rowspan"},
            },
            url_schemes={"http","https","mailto"},
        )

    @field_validator("name", "category", mode="before")
    @classmethod
    def strip_html_text(cls, v):
        return re.sub(r"<[^>]+>", "", v).strip() if v else ""

async def _ensure_templates_table(db):
    # Tabla creada por migrations/init_tables.sql (Fase 3)
    # email_templates + índice
    # Seed de defaults se mantiene:
    # Seed default templates if none exist for __default__
    count = await db.fetchval(
        "SELECT COUNT(*) FROM email_templates WHERE owner = '__default__'"
    )
    if count == 0:
        defaults = [
            (
                "Solicitud de información",
                "Solicitud de información",
                """<p>Estimado/a <strong>[NOMBRE]</strong>,</p>

<p>Reciba un cordial saludo de parte de <strong>Maquita Cushunchic</strong>.</p>
<p>Por medio de la presente, me permito solicitar información sobre <strong>[TEMA]</strong>, con el fin de dar seguimiento a las actividades programadas.</p>
<p>Agradezco de antemano su pronta respuesta y quedo atento/a a cualquier indicación adicional.</p>
<p>Atentamente,</p>
<p><br></p>""",
                "General",
            ),
            (
                "Confirmación de recepción",
                "Confirmación de recepción",
                """<p>Estimado/a <strong>[NOMBRE]</strong>,</p>
<p>Por medio del presente correo, confirmo la recepción de la documentación/información referente a <strong>[TEMA]</strong>, enviada con fecha <strong>[FECHA]</strong>.</p>
<p>En caso de requerir información adicional, no dude en contactarnos.</p>
<p>Agradezco su atención y quedo a su disposición.</p>
<p>Atentamente,</p>
<p><br></p>""",
                "General",
            ),
            (
                "Convocatoria a reunión",
                "Convocatoria a reunión",
                """<p>Estimado/a <strong>[NOMBRE]</strong>,</p>
<p>Reciba un cordial saludo. Me permito convocarle a una reunión de trabajo con los siguientes detalles:</p>
<ul>
<li><strong>Tema:</strong> [TEMA]</li>
<li><strong>Fecha:</strong> [FECHA]</li>
<li><strong>Hora:</strong> [HORA]</li>
<li><strong>Lugar/Enlace:</strong> [LUGAR]</li>
</ul>
<p>Su presencia y participación son de suma importancia para el avance de las actividades planificadas.</p>
<p>Agradezco confirmar su asistencia a la brevedad posible.</p>
<p>Atentamente,</p>
<p><br></p>""",
                "Reuniones",
            ),
        ]
        for name, subject, html_body, category in defaults:
            await db.execute(
                """INSERT INTO email_templates (owner, name, subject, html_body, category)
                   VALUES ('__default__', $1, $2, $3, $4)""",
                name, subject, html_body, category,
            )


@router.get("/templates")
async def list_templates(
    request: Request,
    username: str = Depends(get_current_user),
):
    """List templates for current user (own + defaults)."""
    db = request.app.state.db_pool
    await _ensure_templates_table(db)

    rows = await db.fetch("""
        SELECT id, owner, name, category, subject, html_body, created_at
        FROM email_templates
        WHERE owner = $1 OR owner = '__default__'
        ORDER BY
            CASE WHEN owner = '__default__' THEN 1 ELSE 0 END,
            created_at DESC
    """, username)

    return [
        {
            "id": r["id"],
            "name": r["name"],
            "category": r["category"],
            "subject": r["subject"],
            "html_body": r["html_body"],
            "is_default": r["owner"] == "__default__",
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]


@router.post("/templates")
async def create_template(
    request: Request,
    body: TemplateCreate,
    username: str = Depends(get_current_user),
):
    """Create a new email template for the current user."""
    db = request.app.state.db_pool
    await _ensure_templates_table(db)

    row = await db.fetchrow("""
        INSERT INTO email_templates (owner, name, subject, html_body, category)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, created_at
    """, username, body.name, body.subject, body.html_body, body.category)

    return {
        "status": "created",
        "id": row["id"],
        "created_at": str(row["created_at"]),
    }


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Delete a user-owned template (cannot delete defaults)."""
    db = request.app.state.db_pool
    await _ensure_templates_table(db)

    result = await db.execute("""
        DELETE FROM email_templates
        WHERE id = $1 AND owner = $2
    """, template_id, username)

    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Plantilla no encontrada o es predeterminada")

    return {"status": "deleted", "id": template_id}
