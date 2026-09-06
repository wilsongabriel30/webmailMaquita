"""Endpoints AIR (solo administradores)."""
from fastapi import APIRouter, HTTPException, Request

from app.air import responder
from app.air.engine import run_cycle
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/air", tags=["air"])


async def _require_admin(request: Request):
    user = await get_current_user(request)
    db = request.app.state.db_pool
    row = await db.fetchrow(
        "SELECT 1 FROM admin WHERE username=$1 AND active=true", user)
    if not row:
        raise HTTPException(403, "Requiere administrador")
    return user


@router.get("/incidents")
async def incidents(request: Request, hours: int = 24, ai: bool = True):
    """Investiga (señales + playbook + IA) y devuelve incidentes. NO contiene."""
    await _require_admin(request)
    inc = await run_cycle(request.app.state.db_pool, request.app.state.redis,
                          hours=hours, use_ai=ai, auto_respond=False)
    return {"count": len(inc), "incidents": inc}


@router.post("/run")
async def run(request: Request, hours: int = 24, auto_respond: bool = False):
    """Corre un ciclo. Con auto_respond=true contiene (si threat_config lo permite)."""
    actor = await _require_admin(request)
    inc = await run_cycle(request.app.state.db_pool, request.app.state.redis,
                          hours=hours, use_ai=True, auto_respond=auto_respond)
    return {"count": len(inc), "responded": sum(1 for i in inc if i["responded"]),
            "by": actor, "incidents": inc}


@router.post("/act")
async def act(request: Request):
    """Acción manual desde un incidente: {username, action: lock}."""
    actor = await _require_admin(request)
    body = await request.json()
    username = (body.get("username") or "").strip().lower()
    action = body.get("action")
    if not username or action != "lock":
        raise HTTPException(400, "uso: {username, action:'lock'}")
    res = await responder.lock_account(request.app.state.db_pool, request.app.state.redis,
                                       username, f"acción manual por {actor}", actor=actor, auto=False)
    return res
