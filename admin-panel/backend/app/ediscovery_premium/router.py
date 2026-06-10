"""eDiscovery Premium — admin: custodios + avisos de retención legal.

Construye sobre lo existente: compliance_cases (casos) y legal_holds (la
retención ya respeta los holds activos). Agrega custodios por caso, los pone bajo
hold, les envía un aviso de retención legal y registra el acuse de recibo.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import asyncio
import secrets
import smtplib
import html as html_lib
from email.message import EmailMessage

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/ediscovery-premium", tags=["ediscovery-premium"])
PUBLIC_BASE = "https://mail.example.org"


def _db(r: Request):
    return r.app.state.db


def _send(to_email: str, subject: str, html: str):
    msg = EmailMessage()
    msg["From"] = "Cumplimiento Maquita <cumplimiento@maquita.org>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content("Este aviso requiere un cliente con HTML.")
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP("127.0.0.1", 25, timeout=20) as s:
        s.send_message(msg)


def _notice_html(email: str, title: str, reason: str, url: str) -> str:
    return f"""<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;color:#222">
  <div style="background:#5b5fc7;color:#fff;padding:16px 22px;border-radius:8px 8px 0 0;font-size:18px;font-weight:600">⚖️ Aviso de retención legal</div>
  <div style="border:1px solid #e1dfdd;border-top:none;padding:22px;border-radius:0 0 8px 8px">
    <p>Estimado/a {html_lib.escape(email)},</p>
    <p>Ha sido designado/a <b>custodio</b> en el marco de un proceso de la Fundación Maquita.
    Debe <b>conservar toda la información de su correo</b> relacionada con el asunto y
    <b>no eliminar</b> mensajes hasta nuevo aviso.</p>
    <p style="background:#f3f2fb;border-radius:6px;padding:10px 12px"><b>Caso:</b> {html_lib.escape(title)}<br><b>Motivo:</b> {html_lib.escape(reason)}</p>
    <p style="text-align:center;margin:22px 0"><a href="{url}" style="background:#5b5fc7;color:#fff;text-decoration:none;padding:12px 26px;border-radius:6px;font-weight:600">Leer y confirmar el aviso</a></p>
    <p style="color:#666;font-size:13px">Su buzón ya está bajo retención automática.</p>
  </div></div>"""


# ── Casos ───────────────────────────────────────────────────────────────────
class CaseIn(BaseModel):
    title: str
    reason: str = ""


@router.get("/cases")
async def list_cases(request: Request, admin: dict = Depends(get_current_admin)):
    rows = await _db(request).fetch("""
        SELECT c.id, c.title, c.reason, c.status, c.created_at,
               count(cu.id) AS custodians,
               count(cu.id) FILTER (WHERE cu.acknowledged_at IS NOT NULL) AS acknowledged
        FROM compliance_cases c LEFT JOIN case_custodians cu ON cu.case_id = c.id
        GROUP BY c.id ORDER BY c.created_at DESC LIMIT 100""")
    return {"cases": [{"id": r["id"], "title": r["title"], "reason": r["reason"], "status": r["status"],
                       "custodians": r["custodians"], "acknowledged": r["acknowledged"],
                       "created_at": r["created_at"].isoformat() if r["created_at"] else None} for r in rows]}


@router.post("/cases")
async def create_case(body: CaseIn, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Falta el título")
    cid = await _db(request).fetchval(
        "INSERT INTO compliance_cases (title, reason, case_type, status, created_by) "
        "VALUES ($1,$2,'legal_hold','open',$3) RETURNING id",
        body.title.strip(), body.reason or "Retención legal", admin["username"])
    return {"ok": True, "id": cid}


# ── Custodios ───────────────────────────────────────────────────────────────
class CustodianIn(BaseModel):
    email: str
    place_hold: bool = True
    notify: bool = True


@router.get("/cases/{cid}/custodians")
async def list_custodians(cid: int, request: Request, admin: dict = Depends(get_current_admin)):
    rows = await _db(request).fetch("""
        SELECT cu.id, cu.email, cu.role, cu.hold_id, cu.notified_at, cu.acknowledged_at,
               lh.is_active AS hold_active
        FROM case_custodians cu LEFT JOIN legal_holds lh ON lh.id = cu.hold_id
        WHERE cu.case_id = $1 ORDER BY cu.created_at""", cid)
    return {"custodians": [{"id": r["id"], "email": r["email"], "role": r["role"],
                            "on_hold": bool(r["hold_active"]),
                            "notified": r["notified_at"].isoformat() if r["notified_at"] else None,
                            "acknowledged": r["acknowledged_at"].isoformat() if r["acknowledged_at"] else None}
                           for r in rows]}


@router.post("/cases/{cid}/custodians")
async def add_custodian(cid: int, body: CustodianIn, request: Request,
                        admin: dict = Depends(require_role("superadmin", "admin"))):
    db = _db(request)
    case = await db.fetchrow("SELECT id, title, reason FROM compliance_cases WHERE id = $1", cid)
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    email = (body.email or "").strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Correo no válido")
    exists = await db.fetchval("SELECT 1 FROM case_custodians WHERE case_id=$1 AND email=$2", cid, email)
    if exists:
        raise HTTPException(status_code=400, detail="Ese custodio ya está en el caso")

    hold_id = None
    if body.place_hold:
        hold_id = await db.fetchval(
            "INSERT INTO legal_holds (case_id, mailbox, scope, reason, enabled_by, is_active) "
            "VALUES ($1,$2,'all',$3,$4,true) RETURNING id",
            cid, email, case["reason"] or "Retención legal", admin["username"])

    token = secrets.token_urlsafe(18)
    cust_id = await db.fetchval(
        "INSERT INTO case_custodians (case_id, email, hold_id, ack_token, created_by) "
        "VALUES ($1,$2,$3,$4,$5) RETURNING id", cid, email, hold_id, token, admin["username"])

    notified = False
    if body.notify:
        url = f"{PUBLIC_BASE}/api/hold-ack/{token}"
        html = _notice_html(email, case["title"], case["reason"] or "", url)
        try:
            await asyncio.to_thread(_send, email, f"⚖️ Aviso de retención legal: {case['title']}", html)
            await db.execute("UPDATE case_custodians SET notified_at = now() WHERE id = $1", cust_id)
            notified = True
        except Exception:
            pass
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) VALUES ($1,$2,$3,$4,$5)",
        admin["id"], admin["username"], "custodian_add", f"case {cid}: {email}",
        request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    return {"ok": True, "id": cust_id, "on_hold": hold_id is not None, "notified": notified}


@router.post("/custodians/{cust_id}/notify")
async def renotify(cust_id: int, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    db = _db(request)
    row = await db.fetchrow("""SELECT cu.email, cu.ack_token, cc.title, cc.reason
        FROM case_custodians cu JOIN compliance_cases cc ON cc.id = cu.case_id WHERE cu.id = $1""", cust_id)
    if not row:
        raise HTTPException(status_code=404, detail="No encontrado")
    url = f"{PUBLIC_BASE}/api/hold-ack/{row['ack_token']}"
    html = _notice_html(row["email"], row["title"], row["reason"] or "", url)
    try:
        await asyncio.to_thread(_send, row["email"], f"⚖️ Aviso de retención legal: {row['title']}", html)
        await db.execute("UPDATE case_custodians SET notified_at = now() WHERE id = $1", cust_id)
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo enviar el aviso")
    return {"ok": True}


@router.delete("/custodians/{cust_id}")
async def remove_custodian(cust_id: int, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    db = _db(request)
    row = await db.fetchrow("SELECT hold_id FROM case_custodians WHERE id = $1", cust_id)
    if row and row["hold_id"]:
        await db.execute("UPDATE legal_holds SET is_active=false, released_by=$2, released_at=now() WHERE id=$1",
                         row["hold_id"], admin["username"])
    await db.execute("DELETE FROM case_custodians WHERE id = $1", cust_id)
    return {"ok": True}
