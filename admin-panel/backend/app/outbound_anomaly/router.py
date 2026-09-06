"""
Deteccion de anomalia de envio (cuenta comprometida).
Config + eventos del detector automatico maquita-anomalia-salida.
Autor: Wilson Arguello — Equipo de Tecnologia, Fundacion Maquita.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from app.auth.dependencies import get_current_admin, require_superadmin

router = APIRouter(prefix="/api/outbound-anomaly", tags=["outbound-anomaly"])


def _db(r: Request):
    return r.app.state.db


@router.get("/config")
async def get_config(r: Request, a=Depends(get_current_admin)):
    row = await _db(r).fetchrow(
        "SELECT enabled, window_minutes, threshold_recipients, action, notify_admin "
        "FROM outbound_anomaly_config WHERE id=1")
    return dict(row) if row else {}


class Cfg(BaseModel):
    enabled: bool
    window_minutes: int
    threshold_recipients: int
    action: str
    notify_admin: str


@router.put("/config")
async def put_config(r: Request, body: Cfg, a=Depends(require_superadmin)):
    if body.action not in ("lock", "alert"):
        raise HTTPException(400, "accion invalida (lock|alert)")
    win = max(1, min(120, body.window_minutes))
    thr = max(3, min(5000, body.threshold_recipients))
    await _db(r).execute(
        "UPDATE outbound_anomaly_config SET enabled=$1, window_minutes=$2, "
        "threshold_recipients=$3, action=$4, notify_admin=$5, updated_at=now() WHERE id=1",
        body.enabled, win, thr, body.action, body.notify_admin[:255])
    return {"ok": True}


@router.get("/events")
async def list_events(r: Request, a=Depends(get_current_admin), limit: int = 50):
    limit = max(1, min(200, limit))
    rows = await _db(r).fetch(
        "SELECT id, username, recipients, messages, window_minutes, action, detail, created_at "
        "FROM outbound_anomaly_events ORDER BY created_at DESC LIMIT $1", limit)
    return {"events": [{
        "id": x["id"], "username": x["username"], "recipients": x["recipients"],
        "messages": x["messages"], "window_minutes": x["window_minutes"],
        "action": x["action"], "detail": x["detail"],
        "created_at": x["created_at"].isoformat() if x["created_at"] else None,
    } for x in rows]}
