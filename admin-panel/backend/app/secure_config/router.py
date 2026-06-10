"""Correo cifrado (mensaje seguro / OME) — configuración desde el panel admin.

Activar/desactivar, caducidad, límite de aperturas, texto del portal, y la lista
de mensajes enviados con su estado (abierto / no abierto / caducado / revocado).

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/secure-config", tags=["secure-config"])


def _db(r: Request):
    return r.app.state.db


class SecureConfigIn(BaseModel):
    enabled: bool = True
    expire_days: int = 7
    max_views: int = 0
    intro_text: str = ""


@router.get("")
async def get_config(request: Request, admin: dict = Depends(get_current_admin)):
    row = await _db(request).fetchrow(
        "SELECT enabled, expire_days, max_views, intro_text FROM secure_config WHERE id = 1")
    if not row:
        return {"enabled": True, "expire_days": 7, "max_views": 0, "intro_text": ""}
    return dict(row)


@router.put("")
async def save_config(body: SecureConfigIn, request: Request,
                      admin: dict = Depends(require_role("superadmin", "admin"))):
    expire = max(0, min(int(body.expire_days), 365))
    views = max(0, min(int(body.max_views), 1000))
    await _db(request).execute(
        """
        INSERT INTO secure_config (id, enabled, expire_days, max_views, intro_text, updated_at)
        VALUES (1, $1, $2, $3, $4, now())
        ON CONFLICT (id) DO UPDATE SET
          enabled = EXCLUDED.enabled, expire_days = EXCLUDED.expire_days,
          max_views = EXCLUDED.max_views, intro_text = EXCLUDED.intro_text, updated_at = now()
        """,
        body.enabled, expire, views, (body.intro_text or "")[:1000])
    await _db(request).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) "
        "VALUES ($1,$2,$3,$4,$5)",
        admin["id"], admin["username"], "secure_config_update",
        f"enabled={body.enabled} expire={expire}d",
        request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    return {"ok": True}


@router.get("/messages")
async def list_messages(request: Request, admin: dict = Depends(get_current_admin), limit: int = 50):
    limit = max(1, min(limit, 200))
    rows = await _db(request).fetch(
        "SELECT token, sender, subject, recipients, created_at, expires_at, revoked, "
        "view_count, max_views FROM secure_messages ORDER BY created_at DESC LIMIT $1", limit)
    now = datetime.now(timezone.utc)
    out = []
    for r in rows:
        rec = r["recipients"]
        if isinstance(rec, str):
            try: rec = json.loads(rec)
            except ValueError: rec = []
        if r["revoked"]:
            status = "revocado"
        elif r["expires_at"] and r["expires_at"] < now:
            status = "caducado"
        elif r["view_count"] > 0:
            status = "abierto"
        else:
            status = "no_abierto"
        out.append({
            "token": r["token"], "sender": r["sender"], "subject": r["subject"],
            "recipients": rec, "status": status, "view_count": r["view_count"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
        })
    return {"messages": out}


@router.post("/messages/{token}/revoke")
async def revoke(token: str, request: Request,
                 admin: dict = Depends(require_role("superadmin", "admin"))):
    res = await _db(request).execute("UPDATE secure_messages SET revoked = true WHERE token = $1", token)
    if res.endswith("0"):
        raise HTTPException(status_code=404, detail="No encontrado")
    await _db(request).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) "
        "VALUES ($1,$2,$3,$4,$5)",
        admin["id"], admin["username"], "secure_message_revoke", token[:16],
        request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    return {"ok": True}
