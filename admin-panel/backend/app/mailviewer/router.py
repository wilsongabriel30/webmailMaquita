import asyncio
from asyncio.subprocess import PIPE
from fastapi import APIRouter, Request, Depends, Query, HTTPException
from app.auth.dependencies import get_current_admin, require_role, require_operador
from app.wrappers import doveadm
import json
import re as _re

router = APIRouter(prefix="/api/mailviewer", tags=["mailviewer"],
                   dependencies=[Depends(require_operador)])   # correo ajeno: nunca un viewer (A-18)


def _db(r: Request):
    return r.app.state.db


async def _audit(r, a, action, target=None, details=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""))


async def _run(*cmd) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    out, err = await proc.communicate()
    return out.decode(errors="replace"), err.decode(errors="replace"), proc.returncode


def _parse_fetch_output(out: str, folder: str) -> list[dict]:
    """Parse doveadm fetch output into message list (chronological order)."""
    messages = []
    current: dict = {}
    for line in out.split("\n"):
        if line.startswith("guid: "):
            if current.get("uid"):
                messages.append(current)
            current = {"mailbox_guid": "", "uid": "", "from": "", "to": "",
                       "subject": "", "date": "", "flags": "", "folder": folder}
            current["mailbox_guid"] = line[6:].strip()
        elif line.startswith("uid: "):
            current["uid"] = line[5:].strip()
        elif line.startswith("hdr.subject: "):
            current["subject"] = line[13:].strip()
        elif line.startswith("hdr.from: "):
            current["from"] = line[10:].strip()
        elif line.startswith("hdr.to: "):
            current["to"] = line[8:].strip()
        elif line.startswith("hdr.date: "):
            current["date"] = line[10:].strip()
        elif line.startswith("flags: "):
            current["flags"] = line[7:].strip()
    if current.get("uid"):
        messages.append(current)
    return messages


@router.get("/folders/{username:path}")
async def list_folders(username: str, admin: dict = Depends(get_current_admin)):
    """Listar carpetas de un buzon con estadisticas."""
    statuses = await doveadm.get_mailbox_status(username)
    result = []
    for s in statuses:
        result.append({
            "name": s["mailbox"],
            "messages": s["messages"],
            "unseen": s["unseen"],
            "recent": s["recent"],
        })
    return {"username": username, "folders": result}


@router.get("/messages/{username:path}")
async def list_messages(
    username: str,
    folder: str = Query("INBOX"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(get_current_admin),
):
    """Listar mensajes con paginacion para scroll infinito."""
    out, err, rc = await _run(
        "doveadm", "fetch", "-u", username,
        "guid uid hdr.subject hdr.from hdr.to hdr.date flags",
        "mailbox", folder
    )
    if rc != 0:
        return {"username": username, "folder": folder, "messages": [],
                "total": 0, "offset": offset, "has_more": False}

    messages = _parse_fetch_output(out, folder)

    # Get real mailbox_guid from search
    if messages:
        search_out, _, src = await _run(
            "doveadm", "search", "-u", username, "mailbox", folder,
            "uid", messages[-1]["uid"])
        if src == 0 and search_out.strip():
            real_guid = search_out.strip().split()[0]
            for m in messages:
                m["mailbox_guid"] = real_guid

    total = len(messages)
    # Reverse: newest first
    messages.reverse()
    # Paginate
    page = messages[offset:offset + limit]
    has_more = (offset + limit) < total

    return {
        "username": username, "folder": folder,
        "messages": page, "total": total,
        "offset": offset, "has_more": has_more,
    }


@router.get("/message/{username:path}")
async def read_message(
    username: str,
    mailbox_guid: str = Query(...),
    uid: str = Query(...),
    request: Request = None,
    admin: dict = Depends(require_role("superadmin", "admin")),
):
    """Leer el contenido completo de un mensaje."""
    out, err, rc = await _run(
        "doveadm", "fetch", "-u", username,
        "hdr.subject hdr.from hdr.to hdr.cc hdr.date hdr.message-id flags mailbox body",
        "mailbox-guid", mailbox_guid, "uid", uid)

    if rc != 0:
        raise HTTPException(500, f"Error al leer mensaje: {err}")

    msg = {"headers": {}, "body": ""}
    body_started = False
    body_lines = []

    for line in out.split("\n"):
        if body_started:
            body_lines.append(line)
        elif line.startswith("body:"):
            body_started = True
            rest = line[5:].strip()
            if rest:
                body_lines.append(rest)
        elif line.startswith("hdr."):
            key = line.split(":")[0].replace("hdr.", "")
            val = line.split(":", 1)[1].strip() if ":" in line else ""
            msg["headers"][key] = val
        elif line.startswith("flags:"):
            msg["flags"] = line.split(":", 1)[1].strip()
        elif line.startswith("mailbox:"):
            msg["mailbox"] = line.split(":", 1)[1].strip()

    msg["body"] = "\n".join(body_lines)

    await _audit(request, admin, "mail_read", username, {"uid": uid})
    return msg


@router.post("/move")
async def move_message(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Mover mensaje a otra carpeta."""
    data = await request.json()
    username = data.get("username")
    mailbox_guid = data.get("mailbox_guid")
    uid = data.get("uid")
    destination = data.get("destination", "INBOX")

    if not all([username, mailbox_guid, uid]):
        raise HTTPException(400, "username, mailbox_guid, uid requeridos")

    ok = await doveadm.move_message(username, destination, mailbox_guid, uid)
    if not ok:
        raise HTTPException(500, "Error al mover mensaje")

    await _audit(request, admin, "mail_move", username, {"uid": uid, "to": destination})
    return {"ok": True}


@router.post("/delete")
async def delete_message(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Eliminar un mensaje (mover a Trash)."""
    data = await request.json()
    username = data.get("username")
    mailbox_guid = data.get("mailbox_guid")
    uid = data.get("uid")

    if not all([username, mailbox_guid, uid]):
        raise HTTPException(400, "username, mailbox_guid, uid requeridos")

    ok = await doveadm.move_message(username, "Trash", mailbox_guid, uid)
    await _audit(request, admin, "mail_delete", username, {"uid": uid})
    return {"ok": ok}


@router.get("/search/{username:path}")
async def search_mail(
    username: str,
    q: str = Query("", min_length=1),
    folder: str = Query(""),
    admin: dict = Depends(get_current_admin),
):
    """Buscar mensajes en el buzon de un usuario."""
    query_parts = []
    if folder:
        query_parts.extend(["mailbox", folder])

    if q:
        query_parts.extend(["HEADER", "subject", q])

    if not query_parts:
        query_parts = ["all"]

    query = " ".join(query_parts)
    results = await doveadm.search_messages(username, query)
    results = results[-50:] if len(results) > 50 else results
    results.reverse()

    messages = []
    for msg in results:
        try:
            h = await doveadm.fetch_message_headers(username, msg["mailbox_guid"], msg["uid"])
            h["mailbox_guid"] = msg["mailbox_guid"]
            h["uid"] = msg["uid"]
            messages.append(h)
        except Exception:
            pass

    return {"username": username, "query": q, "messages": messages}


@router.get("/quota/{username:path}")
async def get_quota(username: str, admin: dict = Depends(get_current_admin)):
    """Obtener cuota detallada del usuario."""
    quota = await doveadm.get_quota(username)
    return {"username": username, "quota": quota}
