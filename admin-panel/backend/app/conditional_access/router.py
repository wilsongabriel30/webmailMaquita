"""Panel Acceso Condicional — políticas condición→acción en logins. Admin.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/conditional-access", tags=["conditional-access"])
CONDS = {"riesgo_alto", "pais_no_confiable", "viaje_imposible"}
ACTS = {"bloquear", "requerir_2fa", "alertar"}


def _db(r: Request):
    return r.app.state.db


@router.get("/policies")
async def list_policies(r: Request, a=Depends(get_current_admin)):
    rows = await _db(r).fetch(
        "SELECT id,name,condition,action,enabled FROM conditional_access_policies ORDER BY id")
    return {"policies": [dict(x) for x in rows]}


class PolicyReq(BaseModel):
    name: str
    condition: str
    action: str


@router.post("/policies")
async def create(r: Request, body: PolicyReq, a=Depends(get_current_admin)):
    if body.condition not in CONDS or body.action not in ACTS:
        raise HTTPException(400, "condición o acción inválida")
    pid = await _db(r).fetchval(
        "INSERT INTO conditional_access_policies (name,condition,action,enabled) "
        "VALUES ($1,$2,$3,false) RETURNING id", body.name[:80] or "Política", body.condition, body.action)
    return {"id": pid}


class ToggleReq(BaseModel):
    id: int
    enabled: bool


@router.post("/toggle")
async def toggle(r: Request, body: ToggleReq, a=Depends(get_current_admin)):
    await _db(r).execute("UPDATE conditional_access_policies SET enabled=$1 WHERE id=$2",
                         body.enabled, body.id)
    return {"ok": True}


class IdReq(BaseModel):
    id: int


@router.post("/delete")
async def delete(r: Request, body: IdReq, a=Depends(get_current_admin)):
    await _db(r).execute("DELETE FROM conditional_access_policies WHERE id=$1", body.id)
    return {"ok": True}
