"""Safe Links (protección de enlaces) — configuración desde el panel admin.

Activar/desactivar, reescritura, aviso de sospechosos, lista negra de dominios/
URLs/términos, y registro de clics peligrosos.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import json
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/safelinks-config", tags=["safelinks-config"])


def _db(r: Request):
    return r.app.state.db


class BlockItem(BaseModel):
    pattern: str
    kind: str = "domain"   # domain | url | keyword


class SafeLinksIn(BaseModel):
    enabled: bool = True
    rewrite_enabled: bool = True
    warn_suspicious: bool = True
    block_listed: bool = True
    milter_inbound_enabled: bool = False
    blocklist: list[BlockItem] = []


@router.get("")
async def get_config(request: Request, admin: dict = Depends(get_current_admin)):
    row = await _db(request).fetchrow(
        "SELECT enabled, rewrite_enabled, warn_suspicious, block_listed, milter_inbound_enabled FROM safelinks_config WHERE id = 1")
    cfg = dict(row) if row else {"enabled": True, "rewrite_enabled": True, "warn_suspicious": True, "block_listed": True, "milter_inbound_enabled": False}
    bl = await _db(request).fetch("SELECT pattern, kind, note FROM safelinks_blocklist ORDER BY pattern")
    cfg["blocklist"] = [{"pattern": b["pattern"], "kind": b["kind"], "note": b["note"]} for b in bl]
    return cfg


@router.put("")
async def save_config(body: SafeLinksIn, request: Request,
                      admin: dict = Depends(require_role("superadmin", "admin"))):
    await _db(request).execute(
        """
        INSERT INTO safelinks_config (id, enabled, rewrite_enabled, warn_suspicious, block_listed, milter_inbound_enabled, updated_at)
        VALUES (1, $1, $2, $3, $4, $5, now())
        ON CONFLICT (id) DO UPDATE SET
          enabled=EXCLUDED.enabled, rewrite_enabled=EXCLUDED.rewrite_enabled,
          warn_suspicious=EXCLUDED.warn_suspicious, block_listed=EXCLUDED.block_listed,
          milter_inbound_enabled=EXCLUDED.milter_inbound_enabled, updated_at=now()
        """,
        body.enabled, body.rewrite_enabled, body.warn_suspicious, body.block_listed, body.milter_inbound_enabled)

    # reemplazar lista negra
    seen = set()
    await _db(request).execute("DELETE FROM safelinks_blocklist")
    for it in body.blocklist:
        pat = (it.pattern or "").strip().lower()
        kind = it.kind if it.kind in ("domain", "url", "keyword") else "domain"
        if not pat or (pat, kind) in seen:
            continue
        seen.add((pat, kind))
        await _db(request).execute(
            "INSERT INTO safelinks_blocklist (pattern, kind) VALUES ($1,$2) ON CONFLICT DO NOTHING",
            pat[:255], kind)

    await _db(request).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) VALUES ($1,$2,$3,$4,$5)",
        admin["id"], admin["username"], "safelinks_config_update", f"enabled={body.enabled}",
        request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    return {"ok": True}


@router.get("/clicks")
async def list_clicks(request: Request, admin: dict = Depends(get_current_admin), limit: int = 50):
    limit = max(1, min(limit, 200))
    rows = await _db(request).fetch(
        "SELECT url, host, verdict, proceeded, ip, created_at FROM safelinks_clicks "
        "ORDER BY created_at DESC LIMIT $1", limit)
    return {"clicks": [{
        "url": r["url"], "host": r["host"], "verdict": r["verdict"],
        "proceeded": r["proceeded"], "ip": r["ip"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    } for r in rows]}
