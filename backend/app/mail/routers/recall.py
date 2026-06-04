from app.core.sanitize import strip_html
"""Message recall/retract router — recover sent messages within the same server.

Only works for recipients on local domains (ejemplo.com).
Uses doveadm to search and delete/replace messages in recipient mailboxes.
"""
import subprocess
import re
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.auth.dependencies import get_current_user
from app.config import get_settings

router = APIRouter(prefix="/api/mail", tags=["mail-recall"])


class RecallRequest(BaseModel):
    message_id: str  # The Message-ID header of the sent message
    recipients: list[str]  # List of recipient emails
    action: str = "delete"  # "delete" = remove, "replace" = delete + send new
    replacement_subject: Optional[str] = None
    replacement_html: Optional[str] = None


class RecallResult(BaseModel):
    recipient: str
    status: str  # "recalled", "not_found", "external", "error"
    detail: str


def _validate_email(email: str) -> bool:
    """Validate email format to prevent injection in doveadm args."""
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email))


def _validate_message_id(msg_id: str) -> bool:
    """Validate Message-ID format."""
    return bool(re.match(r"^<[^>\s]{1,500}>$", msg_id)) or bool(re.match(r"^[^\s<>]{1,500}$", msg_id))

def _is_local_domain(email: str, local_domains: list[str]) -> bool:
    """Check if email belongs to a local domain."""
    domain = email.split("@")[-1].lower()
    return domain in [d.lower() for d in local_domains]


def _doveadm_search(recipient: str, message_id: str) -> list[tuple[str, str]]:
    """Search for a message in recipient's mailbox by Message-ID. Returns [(mailbox_guid, uid)]."""
    try:
        result = subprocess.run(
            ["sudo", "doveadm", "search", "-u", recipient, "header", "message-id", message_id],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        matches = []
        for line in result.stdout.strip().split("\n"):
            parts = line.strip().split()
            if len(parts) >= 2:
                matches.append((parts[0], parts[1]))
        return matches
    except Exception:
        return []


def _doveadm_expunge(recipient: str, message_id: str) -> bool:
    """Delete a message from recipient's mailbox by Message-ID."""
    try:
        # doveadm expunge requires MAILBOX in search — try INBOX first, then all common folders
        for folder in ["INBOX", "Sent", "Drafts", "Junk", "Trash", "Archive"]:
            result = subprocess.run(
                ["sudo", "doveadm", "expunge", "-u", recipient, "mailbox", folder, "header", "message-id", message_id],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return True
        return False
    except Exception:
        return False


def _doveadm_fetch_info(recipient: str, message_id: str) -> dict:
    """Fetch message info (subject, date, flags) to confirm before recall."""
    try:
        result = subprocess.run(
            ["sudo", "doveadm", "fetch", "-u", recipient, "uid hdr.subject flags", "header", "message-id", message_id],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {}
        info = {}
        for line in result.stdout.strip().split("\n"):
            if line.startswith("uid:"):
                info["uid"] = line.split(":", 1)[1].strip()
            elif line.startswith("hdr.subject:"):
                info["subject"] = line.split(":", 1)[1].strip()
            elif line.startswith("flags:"):
                info["flags"] = line.split(":", 1)[1].strip()
                info["was_read"] = "\\Seen" in info["flags"]
        return info
    except Exception:
        return {}


async def _send_external_recall_request(
    request, sender: str, recipient: str, msg_id: str, original_msg_id: str
) -> bool:
    """
    Send a recall/retract request to external recipient.
    Uses two methods:
    1. MDN (Message Disposition Notification) requesting deletion
    2. A polite email explaining the recall request
    """
    try:
        from app.mail.clients.smtp_client import send_email, OutgoingEmail
        from app.core.session import get_user_password
        password = await get_user_password(request, sender)

        sender_name = sender.split("@")[0].replace(".", " ").title()

        # Send recall notification email
        recall_email = OutgoingEmail(
            from_addr=sender,
            to=[recipient],
            subject=f"Solicitud de recuperacion: mensaje {original_msg_id}",
            html_body=f"""
            <div style="font-family:Calibri,sans-serif;max-width:600px;margin:0 auto">
                <div style="background:#fff4ce;border:1px solid #f8d22a;border-radius:4px;padding:16px;margin-bottom:16px">
                    <p style="margin:0;font-weight:600;color:#323130">
                        ⚠️ Solicitud de recuperacion de mensaje
                    </p>
                </div>
                <p>Estimado/a destinatario,</p>
                <p><b>{sender_name}</b> ({sender}) solicita la eliminacion del mensaje con ID:</p>
                <p style="font-family:monospace;background:#f3f2f1;padding:8px;border-radius:4px;font-size:12px;word-break:break-all">
                    {original_msg_id}
                </p>
                <p>El remitente indica que este mensaje fue enviado por error o contiene informacion incorrecta.</p>
                <p><b>Por favor, considere eliminar el mensaje original de su buzon.</b></p>
                <hr style="border:none;border-top:1px solid #edebe9;margin:20px 0">
                <p style="font-size:11px;color:#a19f9d">
                    Este es un mensaje automatico generado por el sistema de correo de Maquita.
                    La eliminacion del mensaje original queda a discrecion del destinatario.
                </p>
            </div>
            """,
            text_body=f"Solicitud de recuperacion: {sender_name} ({sender}) solicita la eliminacion del mensaje {original_msg_id}. Por favor elimine el mensaje original.",
        )

        await send_email(recall_email, password)
        return True
    except Exception:
        return False


@router.post("/recall")
async def recall_message(
    request: Request,
    body: RecallRequest,
    username: str = Depends(get_current_user),
):
    """
    Recall/retract a sent message from recipients' mailboxes.

    Only works for recipients on local domains (same mail server).
    External recipients cannot be recalled.

    Actions:
    - "delete": Remove the message from recipient's mailbox
    - "replace": Remove old message and deliver a corrected version
    """
    if not body.message_id:
        raise HTTPException(status_code=400, detail="message_id es requerido")

    if not body.recipients:
        raise HTTPException(status_code=400, detail="recipients es requerido")

    # Normalize message_id — ensure it has angle brackets for doveadm
    msg_id = body.message_id.strip()
    if not msg_id.startswith("<"):
        msg_id = f"<{msg_id}>"

    # Get local domains from DB
    db = request.app.state.db_pool
    domain_rows = await db.fetch("SELECT domain FROM domain WHERE active = true")
    local_domains = [r["domain"] for r in domain_rows if r["domain"] != "ALL"]
    
    # Validar inputs
    if not _validate_message_id(body.message_id):
        raise HTTPException(status_code=422, detail="Message-ID inválido")
    for r in body.recipients:
        if not _validate_email(r):
            raise HTTPException(status_code=422, detail=f"Email inválido: {r}")

    # Verificar que el mensaje existe en la carpeta Sent del usuario (ownership)
    sender_search = subprocess.run(
        ["sudo", "doveadm", "search", "-u", username, "mailbox", "Sent", "header", "message-id", msg_id],
        capture_output=True, text=True, timeout=10,
    )
    if sender_search.returncode != 0 or not sender_search.stdout.strip():
        raise HTTPException(status_code=403, detail="Solo puede recuperar mensajes que usted envio")

    results = []

    for recipient in body.recipients:
        recipient = recipient.strip().lower()

        # External domain — send recall request (like Outlook)
        if not _is_local_domain(recipient, local_domains):
            if body.action == "delete":
                # Send a recall request email to the recipient
                recall_sent = await _send_external_recall_request(
                    request, username, recipient, msg_id, body.message_id
                )
                results.append(RecallResult(
                    recipient=recipient,
                    status="external_request_sent" if recall_sent else "external",
                    detail="Solicitud de recuperacion enviada al destinatario externo. "
                           "NOTA: El servidor destino puede aceptar o rechazar esta solicitud. "
                           "No se garantiza la eliminacion del mensaje."
                           if recall_sent else
                           "Destinatario externo — no se pudo enviar solicitud de recuperacion"
                ))
            else:
                results.append(RecallResult(
                    recipient=recipient,
                    status="external",
                    detail="Destinatario externo — solo se puede enviar solicitud de recuperacion"
                ))
            continue

        # NOTE: We DO allow recalling from own mailbox
        # (useful for self-sent test emails or CC to self)

        # Search for the message
        matches = _doveadm_search(recipient, msg_id)

        if not matches:
            results.append(RecallResult(
                recipient=recipient,
                status="not_found",
                detail="Mensaje no encontrado en el buzon del destinatario (puede haber sido eliminado)"
            ))
            continue

        # Get message info before deleting
        info = _doveadm_fetch_info(recipient, msg_id)
        was_read = info.get("was_read", False)

        # Delete the message
        if body.action in ("delete", "replace"):
            success = _doveadm_expunge(recipient, msg_id)

            if success:
                # If replace: send corrected version
                if body.action == "replace" and body.replacement_html:
                    from app.mail.clients.smtp_client import send_email, OutgoingEmail
                    from app.core.session import get_user_password
                    password = await get_user_password(request, username)

                    corrected = OutgoingEmail(
                        from_addr=username,
                        to=[recipient],
                        subject=body.replacement_subject or info.get("subject", "(Sin asunto)"),
                        html_body=body.replacement_html,
                        text_body="",
                    )
                    try:
                        await send_email(corrected, password)
                    except Exception:
                        pass  # Best effort

                detail = "Mensaje recuperado exitosamente"
                if was_read:
                    detail += " (NOTA: el destinatario ya lo habia leido)"

                results.append(RecallResult(
                    recipient=recipient,
                    status="recalled",
                    detail=detail
                ))
            else:
                results.append(RecallResult(
                    recipient=recipient,
                    status="error",
                    detail="Error al eliminar el mensaje del buzon"
                ))

    # Log the recall action
    try:
        await db.execute(
            "INSERT INTO audit_log (username, action, details, created_at) VALUES ($1, $2, $3, NOW())",
            username,
            "message_recall",
            f"Recalled message {body.message_id} from {len(body.recipients)} recipients. Results: {[r.status for r in results]}"
        )
    except Exception:
        pass  # Non-critical

    # Summary
    recalled_count = sum(1 for r in results if r.status == "recalled")
    external_count = sum(1 for r in results if r.status == "external")

    return {
        "results": [r.model_dump() for r in results],
        "summary": {
            "total": len(results),
            "recalled": recalled_count,
            "external": external_count,
            "not_found": sum(1 for r in results if r.status == "not_found"),
            "errors": sum(1 for r in results if r.status == "error"),
        },
        "message": f"Recuperados: {recalled_count}/{len(results)}" +
                   (f" ({external_count} externos no recuperables)" if external_count else "")
    }


@router.post("/recall/check")
async def check_recallable(
    request: Request,
    body: RecallRequest,
    username: str = Depends(get_current_user),
):
    """
    Check if a message can be recalled before actually doing it.
    Returns status per recipient: can_recall, external, not_found.
    """
    # Normalize message_id
    msg_id = body.message_id.strip()
    if not msg_id.startswith("<"):
        msg_id = f"<{msg_id}>"

    db = request.app.state.db_pool
    domain_rows = await db.fetch("SELECT domain FROM domain WHERE active = true")
    local_domains = [r["domain"] for r in domain_rows if r["domain"] != "ALL"]

    checks = []
    for recipient in body.recipients:
        recipient = recipient.strip().lower()

        if not _is_local_domain(recipient, local_domains):
            checks.append({
                "recipient": recipient,
                "can_recall": False,
                "can_request": True,
                "reason": "Dominio externo — se puede enviar solicitud de recuperacion (no garantizada)",
                "was_read": None,
            })
            continue

        matches = _doveadm_search(recipient, msg_id)
        if not matches:
            checks.append({
                "recipient": recipient,
                "can_recall": False,
                "reason": "Mensaje no encontrado",
                "was_read": None,
            })
            continue

        info = _doveadm_fetch_info(recipient, msg_id)
        checks.append({
            "recipient": recipient,
            "can_recall": True,
            "reason": "Recuperable",
            "was_read": info.get("was_read", None),
            "subject": info.get("subject", ""),
        })

    return {"checks": checks}
