import os
"""Simulación de phishing — gestión de campañas desde el panel admin.

Crear campañas (plantilla + destinatarios), enviarlas, y ver resultados
(enviados / abiertos / clic / entregó credenciales / reportados).

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import asyncio
import secrets
import smtplib
from email.message import EmailMessage

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/phish", tags=["phish"])
PUBLIC_BASE = os.getenv("PUBLIC_BASE", "https://mail.example.org")


def _db(r: Request):
    return r.app.state.db


def _send_mail(from_name: str, from_email: str, to_email: str, subject: str, html: str, token: str = ""):
    msg = EmailMessage()
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["X-Maquita-PhishSim"] = token or "1"
    msg.set_content("Este correo requiere un cliente con HTML.")
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP("127.0.0.1", 25, timeout=20) as s:
        s.send_message(msg)


# ── Plantillas y destinatarios ──────────────────────────────────────────────
@router.get("/templates")
async def templates(request: Request, admin: dict = Depends(get_current_admin)):
    rows = await _db(request).fetch(
        "SELECT id, name, subject, sender_name, sender_email, difficulty FROM phish_templates WHERE active ORDER BY id")
    return {"templates": [dict(r) for r in rows]}


@router.get("/recipients")
async def recipients(request: Request, admin: dict = Depends(get_current_admin)):
    rows = await _db(request).fetch(
        "SELECT username, COALESCE(name,'') AS name FROM mailbox WHERE active ORDER BY username")
    return {"recipients": [{"email": r["username"], "name": r["name"]} for r in rows]}


# ── Campañas ────────────────────────────────────────────────────────────────
class CampaignIn(BaseModel):
    name: str
    template_id: int
    recipients: list[str] = []


@router.get("/campaigns")
async def list_campaigns(request: Request, admin: dict = Depends(get_current_admin)):
    rows = await _db(request).fetch("""
        SELECT c.id, c.name, c.status, c.created_at, c.sent_at, t.name AS template,
               count(tg.id) AS total,
               count(tg.id) FILTER (WHERE tg.sent) AS sent,
               count(tg.id) FILTER (WHERE tg.opened) AS opened,
               count(tg.id) FILTER (WHERE tg.clicked) AS clicked,
               count(tg.id) FILTER (WHERE tg.submitted) AS submitted,
               count(tg.id) FILTER (WHERE tg.reported) AS reported
        FROM phish_campaigns c
        JOIN phish_templates t ON t.id = c.template_id
        LEFT JOIN phish_targets tg ON tg.campaign_id = c.id
        GROUP BY c.id, t.name ORDER BY c.created_at DESC LIMIT 100
    """)
    out = []
    for r in rows:
        d = dict(r)
        d["created_at"] = r["created_at"].isoformat() if r["created_at"] else None
        d["sent_at"] = r["sent_at"].isoformat() if r["sent_at"] else None
        out.append(d)
    return {"campaigns": out}


@router.post("/campaigns")
async def create_campaign(body: CampaignIn, request: Request,
                          admin: dict = Depends(require_role("superadmin", "admin"))):
    if not body.name.strip() or not body.recipients:
        raise HTTPException(status_code=400, detail="Falta nombre o destinatarios")
    tpl = await _db(request).fetchrow("SELECT id FROM phish_templates WHERE id = $1", body.template_id)
    if not tpl:
        raise HTTPException(status_code=400, detail="Plantilla no válida")
    cid = await _db(request).fetchval(
        "INSERT INTO phish_campaigns (name, template_id, created_by, status) VALUES ($1,$2,$3,'borrador') RETURNING id",
        body.name.strip(), body.template_id, admin["username"])
    seen = set()
    for em in body.recipients:
        em = (em or "").strip().lower()
        if not em or em in seen:
            continue
        seen.add(em)
        await _db(request).execute(
            "INSERT INTO phish_targets (campaign_id, email, token) VALUES ($1,$2,$3)",
            cid, em, secrets.token_urlsafe(18))
    return {"ok": True, "id": cid, "targets": len(seen)}


@router.post("/campaigns/{cid}/send")
async def send_campaign(cid: int, request: Request,
                        admin: dict = Depends(require_role("superadmin", "admin"))):
    db = _db(request)
    camp = await db.fetchrow(
        "SELECT c.id, c.name, t.subject, t.html, t.sender_name, t.sender_email "
        "FROM phish_campaigns c JOIN phish_templates t ON t.id = c.template_id WHERE c.id = $1", cid)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    targets = await db.fetch("SELECT id, email, token FROM phish_targets WHERE campaign_id = $1 AND NOT sent", cid)
    sent = 0
    for t in targets:
        link = f"{PUBLIC_BASE}/api/phishtest/{t['token']}"
        pixel = f"{link}/pixel.gif"
        html = camp["html"].replace("{{LINK}}", link).replace("{{PIXEL}}", pixel)
        try:
            await asyncio.to_thread(_send_mail, camp["sender_name"], camp["sender_email"],
                                    t["email"], camp["subject"], html, t["token"])
            await db.execute("UPDATE phish_targets SET sent = true WHERE id = $1", t["id"])
            sent += 1
        except Exception:
            continue
    await db.execute("UPDATE phish_campaigns SET status = 'enviado', sent_at = now() WHERE id = $1", cid)
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) VALUES ($1,$2,$3,$4,$5)",
        admin["id"], admin["username"], "phish_campaign_send", f"#{cid} {camp['name']} ({sent} env)",
        request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    return {"ok": True, "sent": sent}


@router.get("/campaigns/{cid}")
async def campaign_detail(cid: int, request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    camp = await db.fetchrow(
        "SELECT c.id, c.name, c.status, c.created_at, c.sent_at, t.name AS template "
        "FROM phish_campaigns c JOIN phish_templates t ON t.id = c.template_id WHERE c.id = $1", cid)
    if not camp:
        raise HTTPException(status_code=404, detail="No encontrada")
    rows = await db.fetch(
        "SELECT email, sent, opened, clicked, submitted, reported, clicked_at FROM phish_targets "
        "WHERE campaign_id = $1 ORDER BY submitted DESC, clicked DESC, email", cid)
    return {
        "campaign": {**dict(camp),
                     "created_at": camp["created_at"].isoformat() if camp["created_at"] else None,
                     "sent_at": camp["sent_at"].isoformat() if camp["sent_at"] else None},
        "targets": [{"email": r["email"], "sent": r["sent"], "opened": r["opened"],
                     "clicked": r["clicked"], "submitted": r["submitted"], "reported": r["reported"]} for r in rows],
    }


@router.delete("/campaigns/{cid}")
async def delete_campaign(cid: int, request: Request,
                          admin: dict = Depends(require_role("superadmin", "admin"))):
    await _db(request).execute("DELETE FROM phish_campaigns WHERE id = $1", cid)
    return {"ok": True}
