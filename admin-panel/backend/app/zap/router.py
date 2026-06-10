"""ZAP — Zero-hour Auto Purge: panel admin (:8443).

Retira a cuarentena correos ya entregados cuyo enlace resulta malicioso según
los feeds actualizados. NO borra: mueve a cuarentena y se suelta con un clic.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import json
from fastapi import APIRouter, Request, Depends, Query
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role
from app.zap import service

router = APIRouter(prefix="/api/zap", tags=["zap"])


def _db(r: Request):
    return r.app.state.db


async def _audit(r, a, action, target=None, details=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""))


class ZapCfg(BaseModel):
    enabled: bool = False
    enforce: bool = False
    window_hours: int = 48
    include_phishing: bool = False
    max_per_user: int = 200


class ReleaseIn(BaseModel):
    whitelist: bool = False


@router.get("/config")
async def get_config(request: Request, admin: dict = Depends(get_current_admin)):
    row = await _db(request).fetchrow(
        "SELECT enabled, enforce, window_hours, include_phishing, max_per_user FROM zap_config WHERE id = 1")
    return dict(row) if row else ZapCfg().dict()


@router.put("/config")
async def put_config(body: ZapCfg, request: Request,
                     admin: dict = Depends(require_role("superadmin", "admin"))):
    wh = max(1, min(body.window_hours, 720))
    mpu = max(1, min(body.max_per_user, 2000))
    await _db(request).execute(
        """INSERT INTO zap_config (id, enabled, enforce, window_hours, include_phishing, max_per_user, updated_at)
           VALUES (1,$1,$2,$3,$4,$5, now())
           ON CONFLICT (id) DO UPDATE SET enabled=EXCLUDED.enabled, enforce=EXCLUDED.enforce,
             window_hours=EXCLUDED.window_hours, include_phishing=EXCLUDED.include_phishing,
             max_per_user=EXCLUDED.max_per_user, updated_at=now()""",
        body.enabled, body.enforce, wh, body.include_phishing, mpu)
    await _audit(request, admin, "zap_config_update",
                 f"enabled={body.enabled} enforce={body.enforce}")
    return {"ok": True}


@router.post("/scan")
async def run_scan(request: Request, simular: bool = Query(False),
                   admin: dict = Depends(require_role("superadmin", "admin"))):
    """Ejecuta el escaneo. simular=true fuerza modo simulación (no retira)."""
    res = await service.scan(_db(request), force_dry=simular)
    await _audit(request, admin, "zap_scan", None, res)
    return res


@router.get("/actions")
async def list_actions(request: Request, admin: dict = Depends(get_current_admin),
                       status: str = Query("", description="filtro opcional"),
                       limit: int = Query(100, ge=1, le=500)):
    if status:
        rows = await _db(request).fetch(
            "SELECT id, username, subject, sender, bad_host, feed, status, created_at "
            "FROM zap_actions WHERE status=$1 ORDER BY created_at DESC LIMIT $2", status, limit)
    else:
        rows = await _db(request).fetch(
            "SELECT id, username, subject, sender, bad_host, feed, status, created_at "
            "FROM zap_actions ORDER BY created_at DESC LIMIT $1", limit)
    return {"actions": [{
        "id": r["id"], "username": r["username"], "subject": r["subject"],
        "sender": r["sender"], "bad_host": r["bad_host"], "feed": r["feed"],
        "status": r["status"], "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    } for r in rows]}


@router.post("/release/{action_id}")
async def release(action_id: int, body: ReleaseIn, request: Request,
                  admin: dict = Depends(require_role("superadmin", "admin"))):
    """Suelta el correo de cuarentena a la bandeja del usuario."""
    res = await service.release_action(_db(request), action_id, do_whitelist=body.whitelist)
    await _audit(request, admin, "zap_release", str(action_id), res)
    return res


@router.delete("/actions/simulados")
async def clear_sim(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Limpia los registros de simulación (no afecta correos)."""
    n = await _db(request).execute("DELETE FROM zap_actions WHERE status='simulado'")
    return {"ok": True, "deleted": n}
