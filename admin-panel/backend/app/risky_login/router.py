"""Inicios de sesión riesgosos — admin: ver alertas, configurar y actuar.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import json
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/risky-logins", tags=["risky-logins"])


def _db(r: Request):
    return r.app.state.db


@router.get("")
async def list_risky(request: Request, admin: dict = Depends(get_current_admin), status: str = "open", limit: int = 80):
    db = _db(request)
    limit = max(1, min(limit, 200))
    if status == "all":
        rows = await db.fetch("SELECT id, username, ip, country, city, reason, risk, distance_km, status, created_at FROM risky_logins ORDER BY created_at DESC LIMIT $1", limit)
    else:
        rows = await db.fetch("SELECT id, username, ip, country, city, reason, risk, distance_km, status, created_at FROM risky_logins WHERE status=$1 ORDER BY created_at DESC LIMIT $2", status, limit)
    open_n = await db.fetchval("SELECT count(*) FROM risky_logins WHERE status='open'")
    high_n = await db.fetchval("SELECT count(*) FROM risky_logins WHERE status='open' AND risk='high'")
    return {"open_count": open_n or 0, "high_count": high_n or 0,
            "items": [{"id": r["id"], "username": r["username"], "ip": r["ip"], "country": r["country"],
                       "city": r["city"], "reason": r["reason"], "risk": r["risk"], "distance_km": r["distance_km"],
                       "status": r["status"], "created_at": r["created_at"].isoformat() if r["created_at"] else None} for r in rows]}


class StatusIn(BaseModel):
    status: str   # safe | blocked


@router.post("/{rid}/status")
async def set_status(rid: int, body: StatusIn, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    db = _db(request)
    st = body.status if body.status in ("open", "safe", "blocked") else "safe"
    row = await db.fetchrow("UPDATE risky_logins SET status=$1 WHERE id=$2 RETURNING username", st, rid)
    if not row:
        raise HTTPException(status_code=404, detail="No encontrado")
    if st == "blocked":
        await db.execute("UPDATE mailbox SET active=false, modified=now() WHERE username=$1", row["username"])
        await db.execute("INSERT INTO threat_actions (action, target, detail, actor, auto) VALUES ('disable_mailbox',$1,'Deshabilitado por login riesgoso',$2,false)", row["username"], admin["username"])
        await db.execute("UPDATE fraud_alerts SET status='closed' WHERE username=$1 AND alert_type='risky_login' AND status='open'", row["username"])
    return {"ok": True}


# ── Config ──────────────────────────────────────────────────────────────────
class ConfigIn(BaseModel):
    enabled: bool = True
    auto_block: bool = False
    trusted_countries: list[str] = []
    occasional_countries: list[str] = []


@router.get("/config")
async def get_config(request: Request, admin: dict = Depends(get_current_admin)):
    row = await _db(request).fetchrow("SELECT enabled, auto_block, trusted_countries, occasional_countries FROM risky_login_config WHERE id=1")
    if not row:
        return {"enabled": True, "auto_block": False, "trusted_countries": ["Ecuador"], "occasional_countries": []}
    def _l(v):
        if isinstance(v, str):
            try: return json.loads(v)
            except ValueError: return []
        return v or []
    return {"enabled": row["enabled"], "auto_block": row["auto_block"],
            "trusted_countries": _l(row["trusted_countries"]), "occasional_countries": _l(row["occasional_countries"])}


@router.put("/config")
async def put_config(body: ConfigIn, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    tc = sorted({(c or "").strip() for c in body.trusted_countries if (c or "").strip()})
    oc = sorted({(c or "").strip() for c in body.occasional_countries if (c or "").strip()})
    await _db(request).execute(
        "INSERT INTO risky_login_config (id, enabled, auto_block, trusted_countries, occasional_countries, updated_at) VALUES (1,$1,$2,$3,$4,now()) "
        "ON CONFLICT (id) DO UPDATE SET enabled=EXCLUDED.enabled, auto_block=EXCLUDED.auto_block, trusted_countries=EXCLUDED.trusted_countries, occasional_countries=EXCLUDED.occasional_countries, updated_at=now()",
        body.enabled, body.auto_block, json.dumps(tc), json.dumps(oc))
    return {"ok": True}


@router.get("/recent")
async def recent_logins(request: Request, admin: dict = Depends(get_current_admin), limit: int = 30):
    rows = await _db(request).fetch(
        "SELECT username, ip, is_internal, country, city, created_at FROM login_events "
        "WHERE NOT is_internal ORDER BY created_at DESC LIMIT $1", max(1, min(limit, 100)))
    return {"logins": [{"username": r["username"], "ip": r["ip"], "country": r["country"], "city": r["city"],
                        "created_at": r["created_at"].isoformat() if r["created_at"] else None} for r in rows]}
