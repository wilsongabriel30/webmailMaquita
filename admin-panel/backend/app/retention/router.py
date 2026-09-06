"""Panel Retención — políticas de retención de correo (E5 Compliance). Admin.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin

router = APIRouter(prefix="/api/retention", tags=["retention"])


def _db(r: Request):
    return r.app.state.db


@router.get("/policies")
async def list_policies(r: Request, a=Depends(get_current_admin)):
    rows = await _db(r).fetch(
        "SELECT id,name,description,target,folder_pattern,max_age_days,action,move_to,"
        "is_active,messages_affected,last_run FROM retention_policies ORDER BY id")
    return {"policies": [dict(x) for x in rows]}


class PolReq(BaseModel):
    name: str
    description: str = ""
    target: str = "all"
    folder_pattern: str = "*"
    max_age_days: int = 365
    action: str = "delete"
    move_to: str = ""


@router.post("/policies")
async def create(r: Request, body: PolReq, a=Depends(require_superadmin)):
    if body.action not in ("delete", "move"):
        raise HTTPException(400, "acción inválida (delete|move)")
    pid = await _db(r).fetchval(
        "INSERT INTO retention_policies (name,description,target,folder_pattern,max_age_days,"
        "action,move_to,is_active) VALUES ($1,$2,$3,$4,$5,$6,$7,false) RETURNING id",
        (body.name or "Política")[:120], body.description, body.target, body.folder_pattern,
        max(1, body.max_age_days), body.action, body.move_to)
    return {"id": pid}


class ToggleReq(BaseModel):
    id: int
    is_active: bool


@router.post("/toggle")
async def toggle(r: Request, body: ToggleReq, a=Depends(require_superadmin)):
    await _db(r).execute("UPDATE retention_policies SET is_active=$1 WHERE id=$2", body.is_active, body.id)
    return {"ok": True}


class IdReq(BaseModel):
    id: int


@router.post("/delete")
async def delete(r: Request, body: IdReq, a=Depends(require_superadmin)):
    await _db(r).execute("DELETE FROM retention_policies WHERE id=$1", body.id)
    return {"ok": True}
