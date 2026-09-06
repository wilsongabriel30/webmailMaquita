"""API de agentes (solo administradores)."""

from fastapi import APIRouter, HTTPException, Request

from app.agents.runner import list_agents, run_agent
from app.auth.dependencies import get_current_user
from app.config import get_settings

router = APIRouter(prefix="/api/agents", tags=["agents"])


async def _require_admin(request: Request):
    user = await get_current_user(request)
    row = await request.app.state.db_pool.fetchrow(
        "SELECT 1 FROM admin WHERE username=$1 AND active=true", user
    )
    if not row:
        raise HTTPException(403, "Requiere administrador")
    return user


@router.get("")
async def agents(request: Request):
    await _require_admin(request)
    return {"agents": list_agents()}


@router.post("/{name}/run")
async def run(request: Request, name: str, dry_run: bool = True, user: str = ""):
    await _require_admin(request)
    try:
        return await run_agent(
            name,
            request.app.state.db_pool,
            request.app.state.redis,
            get_settings(),
            dry_run=dry_run,
            params={"user": user} if user else None,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
