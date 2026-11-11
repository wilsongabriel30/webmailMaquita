from app.core.sanitize import strip_html

"""Message recall/retract router — recover sent messages within the same server.

Only works for recipients on local domains (ejemplo.com).
Uses doveadm to search and delete/replace messages in recipient mailboxes.
"""
import logging
import re
import subprocess

# [S7-1] Envoltorio con validación propia; sudoers ya no tiene comodines.
MAQUITA_SUDO = "/usr/local/sbin/maquita-sudo"
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.branding.service import marca_corta
from app.config import get_settings
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_pool import get_pooled_imap
from app.mail.services import (
    aviso_envio_por_error,
    plazo_recuperacion,
    recuperar_correo,
)
from app.mail.services.cache_uids import invalidar_uids

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mail", tags=["mail-recall"])


class RecallRequest(BaseModel):
    message_id: str  # The Message-ID header of the sent message
    recipients: list[str]  # List of recipient emails
    action: str = "delete"  # "delete" = remove, "replace" = delete + send new
    replacement_subject: Optional[str] = None
    replacement_html: Optional[str] = None


class RecallResult(BaseModel):
    recipient: str
    # "recalled", "not_found", "external", "external_request_sent", "fuera_de_plazo", "error"
    status: str
    detail: str
    # ¿El destinatario ya lo había leído? (None para externos o no encontrados)
    was_read: Optional[bool] = None
    # Carpetas del destinatario de donde se quitó (vacío si no aplica)
    folders: list[str] = []


def _validate_email(email: str) -> bool:
    """Validate email format to prevent injection in doveadm args."""
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email))


def _validate_message_id(msg_id: str) -> bool:
    """Validate Message-ID format."""
    return bool(re.match(r"^<[^>\s]{1,500}>$", msg_id)) or bool(
        re.match(r"^[^\s<>]{1,500}$", msg_id)
    )


def _is_local_domain(email: str, local_domains: list[str]) -> bool:
    """Check if email belongs to a local domain."""
    domain = email.split("@")[-1].lower()
    return domain in [d.lower() for d in local_domains]


def _doveadm_search(recipient: str, message_id: str) -> list[tuple[str, str]]:
    """Search for a message in recipient's mailbox by Message-ID. Returns [(mailbox_guid, uid)]."""
    try:
        result = subprocess.run(
            [
                "sudo",
                "-n",
                MAQUITA_SUDO,
                "doveadm",
                "search",
                "-u",
                recipient,
                "header",
                "message-id",
                message_id,
            ],
            capture_output=True,
            text=True,
            timeout=10,
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


CARPETAS_HABITUALES = ["INBOX", "Sent", "Drafts", "Junk", "Trash", "Archive"]


def _doveadm_expunge(
    recipient: str, message_id: str, carpetas: Optional[list[str]] = None
) -> bool:
    """Delete a message from recipient's mailbox by Message-ID.

    `carpetas`: las carpetas donde `doveadm fetch` vio el mensaje (todas deben terminar bien).
    Si no se conocen, se recorren las habituales y basta con que alguna exista y responda OK
    (una carpeta inexistente, p. ej. Archive, no debe dar la recuperación por fallida).
    """
    conocidas = bool(carpetas)
    alguna_ok = False
    try:
        # doveadm expunge requires MAILBOX in search
        for folder in carpetas or CARPETAS_HABITUALES:
            result = subprocess.run(
                [
                    "sudo",
                    "-n",
                    MAQUITA_SUDO,
                    "doveadm",
                    "expunge",
                    "-u",
                    recipient,
                    "mailbox",
                    folder,
                    "header",
                    "message-id",
                    message_id,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                alguna_ok = True
            elif conocidas:
                return False
        return alguna_ok
    except Exception:
        return False


def _doveadm_fetch_info(recipient: str, message_id: str) -> dict:
    """Fetch message info (subject, date, flags) to confirm before recall."""
    try:
        result = subprocess.run(
            [
                "sudo",
                "-n",
                MAQUITA_SUDO,
                "doveadm",
                "fetch",
                "-u",
                recipient,
                "mailbox uid hdr.subject flags date.received",
                "header",
                "message-id",
                message_id,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {}
        info = {"folders": []}
        for line in result.stdout.strip().split("\n"):
            if line.startswith("mailbox:"):
                carpeta = line.split(":", 1)[1].strip()
                if carpeta and carpeta not in info["folders"]:
                    info["folders"].append(carpeta)
            elif line.startswith("uid:"):
                info["uid"] = line.split(":", 1)[1].strip()
            elif line.startswith("hdr.subject:"):
                info["subject"] = line.split(":", 1)[1].strip()
            elif line.startswith("flags:"):
                info["flags"] = line.split(":", 1)[1].strip()
                info["was_read"] = "\\Seen" in info["flags"]
            elif line.startswith("date.received:"):
                info["received"] = plazo_recuperacion.mas_antigua(
                    info.get("received"),
                    plazo_recuperacion.interpretar_fecha(line.split(":", 1)[1]),
                )
        return info
    except Exception:
        return {}


def _fecha_en_enviados(username: str, message_id: str):
    """Cuándo se guardó el correo en «Enviados» del remitente (None si no se puede saber)."""
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
                "date.received",
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
            return None
        fecha = None
        for line in result.stdout.split("\n"):
            if line.startswith("date.received:"):
                fecha = plazo_recuperacion.mas_antigua(
                    fecha, plazo_recuperacion.interpretar_fecha(line.split(":", 1)[1])
                )
        return fecha
    except Exception:
        return None


async def _send_external_recall_request(
    request, sender: str, recipient: str, msg_id: str, original_msg_id: str
) -> bool:
    """Destinatario externo: no se puede retirar el correo de un buzón ajeno.

    Se responde en la misma conversación avisando de que el mensaje se envió por error
    (app/mail/services/aviso_envio_por_error.py); el remitente recibe copia como constancia.
    """
    try:
        from app.mail.clients.smtp_client import send_email

        password = await get_user_password(request, sender)
        aviso = aviso_envio_por_error.construir(
            sender,
            recipient,
            msg_id,
            aviso_envio_por_error.asunto_en_enviados(sender, msg_id),
            _fecha_en_enviados(sender, msg_id),
            marca_corta(),
        )
        await send_email(aviso, password)
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
        [
            "sudo",
            "-n",
            MAQUITA_SUDO,
            "doveadm",
            "search",
            "-u",
            username,
            "mailbox",
            "Sent",
            "header",
            "message-id",
            msg_id,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if sender_search.returncode != 0 or not sender_search.stdout.strip():
        raise HTTPException(
            status_code=403, detail="Solo puede recuperar mensajes que usted envió"
        )

    results = []
    fecha_envio = _fecha_en_enviados(username, msg_id)

    for recipient in body.recipients:
        recipient = recipient.strip().lower()

        # External domain — send recall request (like Outlook)
        if not _is_local_domain(recipient, local_domains):
            if plazo_recuperacion.vencido(fecha_envio):
                results.append(
                    RecallResult(
                        recipient=recipient,
                        status=plazo_recuperacion.ESTADO_FUERA_DE_PLAZO,
                        detail=plazo_recuperacion.motivo(fecha_envio),
                    )
                )
                continue
            if body.action == "delete":
                # Send a recall request email to the recipient
                recall_sent = await _send_external_recall_request(
                    request, username, recipient, msg_id, body.message_id
                )
                results.append(
                    RecallResult(
                        recipient=recipient,
                        status="external_request_sent" if recall_sent else "external",
                        detail=(
                            "Destinatario externo: no se puede retirar el correo de su buzón. "
                            "Se le envió, en la misma conversación, el aviso de que el mensaje se envió por error; "
                            "usted recibió una copia como constancia."
                            if recall_sent
                            else "Destinatario externo: no se pudo enviar el aviso de envío por error"
                        ),
                    )
                )
            else:
                results.append(
                    RecallResult(
                        recipient=recipient,
                        status="external",
                        detail="Destinatario externo: solo se puede enviar el aviso de envío por error",
                    )
                )
            continue

        # NOTE: We DO allow recalling from own mailbox
        # (useful for self-sent test emails or CC to self)

        # Search for the message
        matches = _doveadm_search(recipient, msg_id)

        if not matches:
            results.append(
                RecallResult(
                    recipient=recipient,
                    status="not_found",
                    detail="Mensaje no encontrado en el buzón del destinatario (puede haber sido eliminado)",
                )
            )
            continue

        # Get message info before deleting (flags y carpetas reales donde está)
        info = _doveadm_fetch_info(recipient, msg_id)
        was_read = info.get("was_read", False)
        carpetas_mensaje = list(info.get("folders") or [])

        # Plazo máximo (11/11/2026): pasado el plazo no se toca el buzón del destinatario.
        if plazo_recuperacion.vencido(info.get("received")):
            results.append(
                RecallResult(
                    recipient=recipient,
                    status=plazo_recuperacion.ESTADO_FUERA_DE_PLAZO,
                    detail=plazo_recuperacion.motivo(info.get("received")),
                    was_read=bool(was_read),
                )
            )
            continue

        # Delete the message. Decisión de la dirección (09/11/2026): se quita del buzón
        # aunque el destinatario ya lo haya leído; la lectura solo se informa.
        if body.action in ("delete", "replace"):
            success = _doveadm_expunge(recipient, msg_id, carpetas_mensaje or None)

            if success:
                # Sin esto el destinatario seguía viendo el correo en su lista hasta 5 min
                # (caché Redis) y al abrirlo daba «No se pudo abrir el mensaje».
                carpetas = await recuperar_correo.tras_expunge(
                    request.app.state.redis, recipient, carpetas_mensaje
                )
                # If replace: send corrected version
                if body.action == "replace" and body.replacement_html:
                    from app.core.session import get_user_password
                    from app.mail.clients.smtp_client import OutgoingEmail, send_email

                    password = await get_user_password(request, username)

                    corrected = OutgoingEmail(
                        from_addr=username,
                        to=[recipient],
                        subject=body.replacement_subject
                        or info.get("subject", "(Sin asunto)"),
                        html_body=body.replacement_html,
                        text_body="",
                    )
                    try:
                        await send_email(corrected, password)
                    except Exception:
                        pass  # Best effort

                detail = "Recuperado"
                if was_read:
                    detail = "Recuperado (ya lo había leído)"

                results.append(
                    RecallResult(
                        recipient=recipient,
                        status="recalled",
                        detail=detail,
                        was_read=bool(was_read),
                        folders=carpetas,
                    )
                )
            else:
                results.append(
                    RecallResult(
                        recipient=recipient,
                        status="error",
                        detail="Error al eliminar el mensaje del buzón",
                        was_read=bool(was_read),
                    )
                )

    resultados = [r.model_dump() for r in results]

    # Si a todos los destinatarios locales les salió bien, el correo del remitente deja
    # «Enviados» y pasa a «Borradores» para corregirlo y volverlo a enviar (dirección, 09/11/2026).
    movido = {"movido": False}
    if recuperar_correo.decidir_mover_a_borradores(resultados):
        movido = await _mover_enviado_a_borradores(request, username, msg_id)
        if movido.get("movido"):
            await invalidar_uids(
                request.app.state.redis,
                username,
                recuperar_correo.CARPETA_ENVIADOS,
                recuperar_correo.CARPETA_BORRADORES,
            )

    # Rastro de quién recuperó qué (antes fallaba en silencio por una columna inexistente).
    await recuperar_correo.registrar_auditoria(
        db,
        username,
        msg_id,
        resultados,
        ip=request.client.host if request.client else None,
        movido_a_borradores=bool(movido.get("movido")),
    )

    # Summary
    recalled_count = sum(1 for r in results if r.status == "recalled")
    external_count = sum(
        1 for r in results if r.status in recuperar_correo.ESTADOS_EXTERNOS
    )

    mensaje = f"Recuperados: {recalled_count}/{len(results)}"
    if external_count:
        mensaje += f" ({external_count} externos: aviso de envío por error)"
    if movido.get("movido"):
        mensaje = "Mensaje recuperado. Lo encontrará en Borradores para corregirlo y volverlo a enviar."
    fuera_de_plazo = [
        r for r in results if r.status == plazo_recuperacion.ESTADO_FUERA_DE_PLAZO
    ]
    if fuera_de_plazo and recalled_count == 0:
        mensaje = fuera_de_plazo[0].detail

    return {
        "results": resultados,
        "summary": {
            "total": len(results),
            "recalled": recalled_count,
            "external": external_count,
            "not_found": sum(1 for r in results if r.status == "not_found"),
            "errors": sum(1 for r in results if r.status == "error"),
            "fuera_de_plazo": len(fuera_de_plazo),
        },
        "plazo_minutos": plazo_recuperacion.minutos_maximos(),
        "movido_a_borradores": bool(movido.get("movido")),
        "message": mensaje,
    }


async def _mover_enviado_a_borradores(
    request: Request, username: str, msg_id: str
) -> dict:
    """Mueve el correo del remitente de Enviados a Borradores con su propia conexión IMAP."""
    try:
        password = await get_user_password(request, username)
        login_user = await get_imap_login_user(request, username)
        async with get_pooled_imap(login_user, password) as imap:
            return await recuperar_correo.mover_a_borradores(imap, msg_id)
    except Exception as exc:
        logger.warning(
            "recuperación: %s no pudo mover %s a Borradores: %s", username, msg_id, exc
        )
        return {"movido": False, "motivo": str(exc)}


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
    fecha_envio = _fecha_en_enviados(username, msg_id)
    for recipient in body.recipients:
        recipient = recipient.strip().lower()

        if not _is_local_domain(recipient, local_domains):
            if plazo_recuperacion.vencido(fecha_envio):
                checks.append(
                    {
                        "recipient": recipient,
                        "can_recall": False,
                        "can_request": False,
                        "fuera_de_plazo": True,
                        "reason": plazo_recuperacion.motivo(fecha_envio),
                        "was_read": None,
                    }
                )
                continue
            checks.append(
                {
                    "recipient": recipient,
                    "can_recall": False,
                    "can_request": True,
                    "reason": "Externo: no se puede retirar de su buzón; se le enviará el aviso de «enviado por error» en la misma conversación",
                    "was_read": None,
                }
            )
            continue

        matches = _doveadm_search(recipient, msg_id)
        if not matches:
            checks.append(
                {
                    "recipient": recipient,
                    "can_recall": False,
                    "reason": "Mensaje no encontrado",
                    "was_read": None,
                }
            )
            continue

        info = _doveadm_fetch_info(recipient, msg_id)
        was_read = info.get("was_read", None)
        if plazo_recuperacion.vencido(info.get("received")):
            checks.append(
                {
                    "recipient": recipient,
                    "can_recall": False,
                    "fuera_de_plazo": True,
                    "reason": plazo_recuperacion.motivo(info.get("received")),
                    "was_read": was_read,
                }
            )
            continue
        checks.append(
            {
                "recipient": recipient,
                "can_recall": True,
                # Leído o no, se puede recuperar: el texto nunca debe sonar a impedimento.
                "reason": "Recuperable (ya lo leyó)" if was_read else "Recuperable",
                "was_read": was_read,
                "subject": info.get("subject", ""),
                "folders": info.get("folders", []),
            }
        )

    vencidos = [c for c in checks if c.get("fuera_de_plazo")]
    return {
        "checks": checks,
        "plazo_minutos": plazo_recuperacion.minutos_maximos(),
        # Aviso para mostrar en pantalla cuando ya no se puede recuperar a nadie por el plazo.
        "aviso": (
            vencidos[0]["reason"]
            if vencidos
            and not any(c.get("can_recall") or c.get("can_request") for c in checks)
            else None
        ),
    }
