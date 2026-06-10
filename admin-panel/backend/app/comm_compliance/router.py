"""Communication Compliance — admin: políticas + cola de revisión.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import json
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/comm-compliance", tags=["comm-compliance"])


def _db(r: Request):
    return r.app.state.db


class PolicyIn(BaseModel):
    name: str
    description: str = ""
    terms: list[str] = []
    scope: str = "outbound"      # outbound | inbound | all
    severity: str = "media"
    enabled: bool = False


def _norm_terms(terms):
    return sorted({(t or "").strip() for t in terms if (t or "").strip()})


@router.get("/policies")
async def list_policies(request: Request, admin: dict = Depends(get_current_admin)):
    rows = await _db(request).fetch("SELECT id, name, description, terms, scope, severity, enabled FROM comm_policies ORDER BY id")
    out = []
    for r in rows:
        terms = r["terms"]
        if isinstance(terms, str):
            try: terms = json.loads(terms)
            except ValueError: terms = []
        out.append({"id": r["id"], "name": r["name"], "description": r["description"],
                    "terms": terms, "scope": r["scope"], "severity": r["severity"], "enabled": r["enabled"]})
    return {"policies": out}


@router.post("/policies")
async def create_policy(body: PolicyIn, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Falta el nombre")
    scope = body.scope if body.scope in ("outbound", "inbound", "all") else "outbound"
    sev = body.severity if body.severity in ("baja", "media", "alta") else "media"
    pid = await _db(request).fetchval(
        "INSERT INTO comm_policies (name, description, terms, scope, severity, enabled) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
        body.name.strip(), body.description, json.dumps(_norm_terms(body.terms)), scope, sev, body.enabled)
    return {"ok": True, "id": pid}


@router.put("/policies/{pid}")
async def update_policy(pid: int, body: PolicyIn, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    scope = body.scope if body.scope in ("outbound", "inbound", "all") else "outbound"
    sev = body.severity if body.severity in ("baja", "media", "alta") else "media"
    res = await _db(request).execute(
        "UPDATE comm_policies SET name=$1, description=$2, terms=$3, scope=$4, severity=$5, enabled=$6 WHERE id=$7",
        body.name.strip(), body.description, json.dumps(_norm_terms(body.terms)), scope, sev, body.enabled, pid)
    if res.endswith("0"):
        raise HTTPException(status_code=404, detail="No encontrada")
    return {"ok": True}


@router.delete("/policies/{pid}")
async def delete_policy(pid: int, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    await _db(request).execute("DELETE FROM comm_policies WHERE id=$1", pid)
    return {"ok": True}


@router.get("/flags")
async def list_flags(request: Request, admin: dict = Depends(get_current_admin), status: str = "open", limit: int = 60):
    limit = max(1, min(limit, 200))
    if status == "all":
        rows = await _db(request).fetch(
            "SELECT id, policy_name, username, direction, recipients, subject, snippet, matched_terms, severity, status, created_at "
            "FROM comm_flags ORDER BY created_at DESC LIMIT $1", limit)
    else:
        rows = await _db(request).fetch(
            "SELECT id, policy_name, username, direction, recipients, subject, snippet, matched_terms, severity, status, created_at "
            "FROM comm_flags WHERE status=$1 ORDER BY created_at DESC LIMIT $2", status, limit)
    out = []
    for r in rows:
        rec = r["recipients"]; mt = r["matched_terms"]
        if isinstance(rec, str):
            try: rec = json.loads(rec)
            except ValueError: rec = []
        if isinstance(mt, str):
            try: mt = json.loads(mt)
            except ValueError: mt = []
        out.append({"id": r["id"], "policy_name": r["policy_name"], "username": r["username"],
                    "direction": r["direction"], "recipients": rec, "subject": r["subject"],
                    "snippet": r["snippet"], "matched_terms": mt, "severity": r["severity"], "status": r["status"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None})
    open_count = await _db(request).fetchval("SELECT count(*) FROM comm_flags WHERE status='open'")
    return {"flags": out, "open_count": open_count or 0}


class StatusIn(BaseModel):
    status: str   # reviewed | escalated | dismissed


@router.post("/flags/{fid}/status")
async def set_status(fid: int, body: StatusIn, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    st = body.status if body.status in ("open", "reviewed", "escalated", "dismissed") else "reviewed"
    await _db(request).execute(
        "UPDATE comm_flags SET status=$1, reviewed_by=$2, reviewed_at=now() WHERE id=$3",
        st, admin["username"], fid)
    return {"ok": True}
