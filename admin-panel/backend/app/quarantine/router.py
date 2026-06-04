import json
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from app.auth.dependencies import get_current_admin, require_role
from app.wrappers import rspamd, doveadm

router = APIRouter(prefix="/api/quarantine", tags=["quarantine"])

def _db(r: Request): return r.app.state.db
async def _audit(r, a, action, target=None, details=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""))


@router.get("/history")
async def spam_history(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin: dict = Depends(get_current_admin),
):
    """Historial de correos procesados por Rspamd."""
    rows = await rspamd.get_history(offset=offset, limit=limit)
    return {"rows": rows, "offset": offset, "limit": limit}


@router.get("/stats")
async def spam_stats(admin: dict = Depends(get_current_admin)):
    """Estadisticas de Rspamd."""
    return await rspamd.get_stat()


@router.get("/junk/{username:path}")
async def list_junk(username: str, admin: dict = Depends(get_current_admin)):
    """Listar correos en carpetas de spam de un usuario."""
    # Auto-append domain if not provided
    if "@" not in username:
        db = _db(admin.get("_request") if isinstance(admin, dict) else None)
        username = username + "@maquita.org"

    spam_folders = ["Junk", "Spam", "Correo electr\u00f3nico no deseado", "Unwanted"]
    all_msgs = []

    for folder in spam_folders:
        try:
            results = await doveadm.search_messages(username, f"mailbox {folder}")
            # Limit to 50 per folder for performance
            for msg in results[:50]:
                try:
                    h = await doveadm.fetch_message_headers(username, msg["mailbox_guid"], msg["uid"])
                    h["mailbox_guid"] = msg["mailbox_guid"]
                    h["uid"] = msg["uid"]
                    h["spam_folder"] = folder
                    all_msgs.append(h)
                except Exception:
                    pass
                if len(all_msgs) >= 100:
                    break
        except Exception:
            continue
        if len(all_msgs) >= 100:
            break

    return {"username": username, "messages": all_msgs, "total_found": len(all_msgs)}


@router.post("/release")
async def release_from_spam(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Mover correo de spam a inbox (marcar como ham)."""
    data = await request.json()
    username = data.get("username")
    mailbox_guid = data.get("mailbox_guid")
    uid = data.get("uid")

    if not all([username, mailbox_guid, uid]):
        raise HTTPException(400, "username, mailbox_guid y uid requeridos")

    ok = await doveadm.move_message(username, "INBOX", mailbox_guid, uid)
    if not ok:
        raise HTTPException(500, "Error al mover mensaje")

    await _audit(request, admin, "spam_release", username, {"uid": uid})
    return {"ok": True}


@router.post("/mark-spam")
async def mark_as_spam(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Mover correo a spam."""
    data = await request.json()
    username = data.get("username")
    mailbox_guid = data.get("mailbox_guid")
    uid = data.get("uid")

    if not all([username, mailbox_guid, uid]):
        raise HTTPException(400, "username, mailbox_guid y uid requeridos")

    ok = await doveadm.move_message(username, "Junk", mailbox_guid, uid)
    await _audit(request, admin, "spam_mark", username, {"uid": uid})
    return {"ok": ok}


@router.get("/errors")
async def rspamd_errors(admin: dict = Depends(get_current_admin)):
    return await rspamd.get_errors()
