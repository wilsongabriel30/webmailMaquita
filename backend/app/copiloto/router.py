"""API de Copiloto de Seguridad (solo administradores)."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.copiloto.asistente import ask

router = APIRouter(prefix="/api/copiloto", tags=["copiloto"])


async def _require_admin(request: Request):
    user = await get_current_user(request)
    row = await request.app.state.db_pool.fetchrow(
        "SELECT 1 FROM admin WHERE username=$1 AND active=true", user
    )
    if not row:
        raise HTTPException(403, "Requiere administrador")
    return user


class AskReq(BaseModel):
    question: str
    days: int = 7


@router.post("/ask")
async def ask_endpoint(request: Request, body: AskReq):
    await _require_admin(request)
    q = (body.question or "").strip()
    if not q:
        raise HTTPException(400, "pregunta vacía")
    return await ask(request.app.state.db_pool, q, days=max(1, min(body.days, 90)))
