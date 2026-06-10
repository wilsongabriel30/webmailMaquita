"""Safe Attachments — panel admin (:8443). Analiza adjuntos y retira a cuarentena
(reversible) los correos con adjuntos maliciosos. Arranca APAGADO y en SIMULACION.
"""
import json
from fastapi import APIRouter, Request, Depends, Query
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role
from app.safeattach import service

router = APIRouter(prefix="/api/safeattach", tags=["safeattach"])


def _db(r: Request):
    return r.app.state.db


async def _audit(r, a, action, target=None, details=None):
    try:
        await _db(r).execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
            "VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
            a["id"], a["username"], action, target, json.dumps(details) if details else None,
            r.headers.get("X-Real-IP", r.client.host if r.client else ""))
    except Exception:
        pass


class SaCfg(BaseModel):
    enabled: bool
    enforce: bool
    window_hours: int = 24
    max_per_user: int = 200
    quarantine_folder: str = "Junk"
    quarantine_suspicious: bool = False
    scan_archives: bool = True


@router.get("/config")
async def get_config(r: Request, a=Depends(get_current_admin)):
    row = await _db(r).fetchrow("SELECT * FROM safeattach_config WHERE id=1")
    return dict(row) if row else {}


@router.put("/config")
async def put_config(r: Request, cfg: SaCfg, a=Depends(require_role("admin"))):
    await _db(r).execute(
        "UPDATE safeattach_config SET enabled=$1, enforce=$2, window_hours=$3, max_per_user=$4, "
        "quarantine_folder=$5, quarantine_suspicious=$6, scan_archives=$7, updated_at=now() WHERE id=1",
        cfg.enabled, cfg.enforce, cfg.window_hours, cfg.max_per_user,
        cfg.quarantine_folder, cfg.quarantine_suspicious, cfg.scan_archives)
    await _audit(r, a, "safeattach_config", details=cfg.dict())
    return {"ok": True}


@router.post("/scan")
async def scan_now(r: Request, user: str | None = Query(None),
                   dry: bool = Query(True), a=Depends(require_role("admin"))):
    """Escanea ahora. dry=True fuerza simulación aunque la config esté en enforce."""
    res = await service.scan(_db(r), only_user=user, force_dry=dry)
    await _audit(r, a, "safeattach_scan", details={"user": user, "dry": dry, "res": res})
    return res


@router.get("/results")
async def list_results(r: Request, status: str | None = Query(None),
                       limit: int = Query(200, le=1000), a=Depends(get_current_admin)):
    q = "SELECT * FROM safeattach_results"
    args = []
    if status:
        q += " WHERE status=$1"
        args.append(status)
    q += " ORDER BY created_at DESC LIMIT " + str(int(limit))
    rows = await _db(r).fetch(q, *args)
    return [dict(x) for x in rows]


@router.post("/release/{action_id}")
async def release(r: Request, action_id: int, a=Depends(require_role("admin"))):
    res = await service.release_action(_db(r), action_id)
    await _audit(r, a, "safeattach_release", target=str(action_id), details=res)
    return res


@router.get("/stats")
async def stats(r: Request, a=Depends(get_current_admin)):
    row = await _db(r).fetchrow(
        "SELECT count(*) FILTER (WHERE status='simulado') AS simulado, "
        "count(*) FILTER (WHERE status='cuarentena') AS cuarentena, "
        "count(*) FILTER (WHERE status='liberado') AS liberado, "
        "count(*) FILTER (WHERE verdict='malicious') AS maliciosos, "
        "count(*) FILTER (WHERE verdict='suspicious') AS sospechosos FROM safeattach_results")
    return dict(row) if row else {}
