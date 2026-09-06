import json
from fastapi import APIRouter, Request, HTTPException, Depends
from app.auth.dependencies import get_current_admin, require_role, require_operador
from app.wrappers import doveadm

router = APIRouter(prefix="/api/recovery", tags=["recovery"],
                   dependencies=[Depends(require_operador)])   # correo ajeno: nunca un viewer (A-18)

def _db(r: Request): return r.app.state.db
async def _audit(r, a, action, target=None, details=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""))


@router.get("/trash/{username:path}")
async def list_trash(username: str, admin: dict = Depends(get_current_admin)):
    """Listar correos en papelera de un usuario."""
    trash_folders = ["Trash", "Elementos eliminados", "Deleted Items", "Papelera"]
    all_messages = []

    for folder in trash_folders:
        try:
            results = await doveadm.search_messages(username, f"mailbox {folder}")
            for msg in results:
                try:
                    headers = await doveadm.fetch_message_headers(username, msg["mailbox_guid"], msg["uid"])
                    headers["mailbox_guid"] = msg["mailbox_guid"]
                    headers["uid"] = msg["uid"]
                    headers["trash_folder"] = folder
                    all_messages.append(headers)
                except Exception:
                    pass
        except Exception:
            continue

    return {"username": username, "messages": all_messages[:100]}


@router.post("/restore")
async def restore_message(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Restaurar correo de papelera a bandeja de entrada."""
    data = await request.json()
    username = data.get("username")
    mailbox_guid = data.get("mailbox_guid")
    uid = data.get("uid")
    dest = data.get("destination", "INBOX")

    if not all([username, mailbox_guid, uid]):
        raise HTTPException(400, "username, mailbox_guid y uid requeridos")

    ok = await doveadm.move_message(username, dest, mailbox_guid, uid)
    if not ok:
        raise HTTPException(500, "Error al restaurar mensaje")

    await _audit(request, admin, "mail_restore", username, {"uid": uid, "dest": dest})
    return {"ok": True, "moved_to": dest}


@router.post("/restore-bulk")
async def restore_bulk(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Restaurar multiples correos."""
    data = await request.json()
    username = data.get("username")
    messages = data.get("messages", [])
    dest = data.get("destination", "INBOX")
    restored = 0
    errors = 0

    for msg in messages:
        try:
            ok = await doveadm.move_message(username, dest, msg["mailbox_guid"], msg["uid"])
            if ok:
                restored += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    await _audit(request, admin, "mail_restore_bulk", username, {"count": restored, "dest": dest})
    return {"restored": restored, "errors": errors}


@router.get("/search/{username:path}")
async def search_all_mail(username: str, query: str = "all", admin: dict = Depends(get_current_admin)):
    """Buscar correos en todos los buzones de un usuario."""
    results = await doveadm.search_messages(username, query)
    messages = []
    for msg in results[:50]:
        try:
            h = await doveadm.fetch_message_headers(username, msg["mailbox_guid"], msg["uid"])
            h["mailbox_guid"] = msg["mailbox_guid"]
            h["uid"] = msg["uid"]
            messages.append(h)
        except Exception:
            pass
    return {"username": username, "messages": messages}
