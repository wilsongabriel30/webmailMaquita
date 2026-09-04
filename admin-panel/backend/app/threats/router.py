"""Panel de amenazas + respuesta automática (AIR) — admin.

Agrega datos reales (mail_trace, spam_analysis, user_activity_log, safelinks_clicks,
fraud_alerts) y ofrece acciones que SÍ se aplican: bloquear remitente en rspamd,
deshabilitar buzón comprometido, y respuesta automática configurable.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import asyncio
import json
import subprocess
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role
from app.wrappers.privilegios import con_sudo

router = APIRouter(prefix="/api/threats", tags=["threats"])
RSPAMD_MAP = "/etc/rspamd/local.d/maps/blacklist_domains.map"
WINDOW = "30 days"   # los datos de mail_trace pueden no ser de hoy


def _db(r: Request):
    return r.app.state.db


async def _audit(r, a, action, target="", details=None):
    try:
        await _db(r).execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) VALUES ($1,$2,$3,$4,$5)",
            a["id"], a["username"], action, target,
            r.headers.get("X-Real-IP", r.client.host if r.client else ""))
    except Exception:
        pass


@router.get("/summary")
async def summary(request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    q = lambda sql: db.fetchval(sql)
    spam_blocked = await q("SELECT count(*) FROM spam_analysis WHERE is_spam") or 0
    auth_fail = await q(f"""SELECT count(*) FROM mail_trace
        WHERE created_at > now() - interval '{WINDOW}'
        AND (dmarc_result='fail' OR spf_result='fail')""") or 0
    login_fail = await q(f"""SELECT count(*) FROM user_activity_log
        WHERE created_at > now() - interval '{WINDOW}' AND action='login_failed'""") or 0
    bad_clicks = await q(f"""SELECT count(*) FROM safelinks_clicks
        WHERE created_at > now() - interval '{WINDOW}' AND verdict IN ('suspicious','blocked')""") or 0
    acct_alerts = await q("SELECT count(*) FROM fraud_alerts WHERE status='open'") or 0
    return {"window": WINDOW, "spam_blocked": spam_blocked, "auth_fail": auth_fail,
            "login_fail": login_fail, "bad_clicks": bad_clicks, "acct_alerts": acct_alerts}


@router.get("/feed")
async def feed(request: Request, admin: dict = Depends(get_current_admin), limit: int = 40):
    db = _db(request)
    items = []
    # Correos rechazados / spam
    for r in await db.fetch(f"""SELECT created_at, sender, recipient, rspamd_action, rspamd_score, status, dmarc_result
        FROM mail_trace WHERE created_at > now() - interval '{WINDOW}'
        AND (rspamd_action IN ('reject','quarantine') OR status='reject' OR dmarc_result='fail')
        ORDER BY created_at DESC LIMIT $1""", limit):
        items.append({"type": "correo", "when": r["created_at"].isoformat() if r["created_at"] else None,
                      "source": r["sender"] or "(desconocido)",
                      "detail": f"{r['rspamd_action'] or r['status']}" + (f" · score {r['rspamd_score']:.1f}" if r["rspamd_score"] is not None else "") + (" · DMARC fail" if r["dmarc_result"] == "fail" else ""),
                      "severity": "high" if (r["rspamd_action"] == "reject" or r["status"] == "reject") else "medium"})
    # Clics peligrosos
    for r in await db.fetch(f"""SELECT created_at, host, url, verdict, proceeded FROM safelinks_clicks
        WHERE created_at > now() - interval '{WINDOW}' AND verdict IN ('suspicious','blocked')
        ORDER BY created_at DESC LIMIT $1""", limit):
        items.append({"type": "enlace", "when": r["created_at"].isoformat() if r["created_at"] else None,
                      "source": r["host"] or r["url"], "detail": f"{r['verdict']}" + (" · continuó ⚠️" if r["proceeded"] else ""),
                      "severity": "high" if r["verdict"] == "blocked" else "medium"})
    # Alertas de cuenta
    for r in await db.fetch("SELECT created_at, username, alert_type, description, severity FROM fraud_alerts WHERE status='open' ORDER BY created_at DESC LIMIT $1", limit):
        items.append({"type": "cuenta", "when": r["created_at"].isoformat() if r["created_at"] else None,
                      "source": r["username"] or "", "detail": f"{r['alert_type']}: {r['description']}", "severity": r["severity"] or "high"})
    # Logins fallidos (agrupados por usuario)
    for r in await db.fetch(f"""SELECT max(created_at) AS last, username, count(*) AS n FROM user_activity_log
        WHERE created_at > now() - interval '{WINDOW}' AND action='login_failed'
        GROUP BY username HAVING count(*) >= 3 ORDER BY n DESC LIMIT 15"""):
        items.append({"type": "acceso", "when": r["last"].isoformat() if r["last"] else None,
                      "source": r["username"] or "", "detail": f"{r['n']} intentos de acceso fallidos", "severity": "medium" if r["n"] < 10 else "high"})
    items.sort(key=lambda x: x["when"] or "", reverse=True)
    return {"items": items[:limit]}


@router.get("/top-senders")
async def top_senders(request: Request, admin: dict = Depends(get_current_admin)):
    rows = await _db(request).fetch(f"""SELECT sender, count(*) AS n, max(rspamd_score) AS max_score
        FROM mail_trace WHERE created_at > now() - interval '{WINDOW}'
        AND (rspamd_action IN ('reject','quarantine') OR status='reject') AND sender IS NOT NULL AND sender <> ''
        GROUP BY sender ORDER BY n DESC LIMIT 12""")
    return {"senders": [{"sender": r["sender"], "count": r["n"], "max_score": r["max_score"]} for r in rows]}


# ── Respuesta automática (config) ───────────────────────────────────────────
class ThreatConfigIn(BaseModel):
    auto_disable_on_compromise: bool = False
    auto_block_dmarc_reject: bool = False


@router.get("/config")
async def get_config(request: Request, admin: dict = Depends(get_current_admin)):
    row = await _db(request).fetchrow("SELECT auto_disable_on_compromise, auto_block_dmarc_reject FROM threat_config WHERE id=1")
    return dict(row) if row else {"auto_disable_on_compromise": False, "auto_block_dmarc_reject": False}


@router.put("/config")
async def put_config(body: ThreatConfigIn, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    await _db(request).execute(
        "INSERT INTO threat_config (id, auto_disable_on_compromise, auto_block_dmarc_reject, updated_at) "
        "VALUES (1,$1,$2,now()) ON CONFLICT (id) DO UPDATE SET "
        "auto_disable_on_compromise=EXCLUDED.auto_disable_on_compromise, auto_block_dmarc_reject=EXCLUDED.auto_block_dmarc_reject, updated_at=now()",
        body.auto_disable_on_compromise, body.auto_block_dmarc_reject)
    await _audit(request, admin, "threat_config_update", f"autodisable={body.auto_disable_on_compromise}")
    return {"ok": True}


# ── Acciones reales ─────────────────────────────────────────────────────────
class BlockSenderIn(BaseModel):
    pattern: str
    note: str = ""


def _rspamd_block(pattern: str, who: str):
    with open(RSPAMD_MAP, "a") as f:
        f.write(f"{pattern}  # bloqueado por {who}\n")
    subprocess.run(list(con_sudo("systemctl", "reload", "rspamd")), timeout=15, capture_output=True)


@router.post("/block-sender")
async def block_sender(body: BlockSenderIn, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    pat = (body.pattern or "").strip().lower().lstrip("@")
    if not pat or "." not in pat:
        raise HTTPException(status_code=400, detail="Indica un dominio válido (ej. malicioso.com)")
    db = _db(request)
    await db.execute("INSERT INTO blocked_senders (pattern, note, created_by) VALUES ($1,$2,$3) ON CONFLICT (pattern) DO NOTHING",
                     pat, body.note, admin["username"])
    rspamd_ok = True
    try:
        await asyncio.to_thread(_rspamd_block, pat, admin["username"])
    except Exception:
        rspamd_ok = False
    await db.execute("INSERT INTO threat_actions (action, target, detail, actor, auto) VALUES ('block_sender',$1,$2,$3,false)",
                     pat, body.note or "", admin["username"])
    await _audit(request, admin, "block_sender", pat)
    return {"ok": True, "rspamd_reloaded": rspamd_ok}


@router.get("/blocked-senders")
async def blocked_senders(request: Request, admin: dict = Depends(get_current_admin)):
    rows = await _db(request).fetch("SELECT id, pattern, note, created_by, created_at FROM blocked_senders ORDER BY created_at DESC")
    return {"senders": [{"id": r["id"], "pattern": r["pattern"], "note": r["note"],
                         "created_by": r["created_by"],
                         "created_at": r["created_at"].isoformat() if r["created_at"] else None} for r in rows]}


class MailboxIn(BaseModel):
    username: str


@router.post("/disable-mailbox")
async def disable_mailbox(body: MailboxIn, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    db = _db(request)
    row = await db.fetchrow("UPDATE mailbox SET active=false, modified=now() WHERE username=$1 RETURNING username", body.username)
    if not row:
        raise HTTPException(status_code=404, detail="Buzón no encontrado")
    await db.execute("INSERT INTO threat_actions (action, target, detail, actor, auto) VALUES ('disable_mailbox',$1,'Deshabilitado manualmente',$2,false)",
                     body.username, admin["username"])
    await _audit(request, admin, "disable_mailbox", body.username)
    return {"ok": True}


@router.post("/enable-mailbox")
async def enable_mailbox(body: MailboxIn, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    db = _db(request)
    await db.execute("UPDATE mailbox SET active=true, modified=now() WHERE username=$1", body.username)
    await db.execute("INSERT INTO threat_actions (action, target, detail, actor, auto) VALUES ('enable_mailbox',$1,'Reactivado',$2,false)",
                     body.username, admin["username"])
    # cerrar alertas de esa cuenta
    await db.execute("UPDATE fraud_alerts SET status='closed', closed_by=$2, closed_at=now() WHERE username=$1 AND status='open'", body.username, admin["username"])
    await _audit(request, admin, "enable_mailbox", body.username)
    return {"ok": True}


@router.get("/actions")
async def actions(request: Request, admin: dict = Depends(get_current_admin), limit: int = 30):
    rows = await _db(request).fetch("SELECT action, target, detail, actor, auto, created_at FROM threat_actions ORDER BY created_at DESC LIMIT $1", max(1, min(limit, 100)))
    return {"actions": [{"action": r["action"], "target": r["target"], "detail": r["detail"],
                         "actor": r["actor"], "auto": r["auto"],
                         "created_at": r["created_at"].isoformat() if r["created_at"] else None} for r in rows]}
