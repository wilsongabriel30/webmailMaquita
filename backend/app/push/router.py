# -*- coding: utf-8 -*-
"""Endpoints de Web Push: clave pública VAPID + alta/baja de suscripción."""
from fastapi import APIRouter, Request, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.push import service

router = APIRouter(prefix="/api/push", tags=["push"])


@router.get("/vapid-public-key")
async def vapid_public_key():
    return {"key": service.VAPID_PUBLIC, "enabled": service.habilitado()}


@router.post("/subscribe")
async def subscribe(request: Request, username: str = Depends(get_current_user)):
    body = await request.json()
    endpoint = (body or {}).get("endpoint")
    keys = (body or {}).get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        raise HTTPException(status_code=400, detail="Suscripción inválida")
    await service.guardar(request.app.state.db_pool, username, endpoint, keys["p256dh"], keys["auth"])
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(request: Request, username: str = Depends(get_current_user)):
    body = await request.json()
    endpoint = (body or {}).get("endpoint")
    if endpoint:
        await service.borrar(request.app.state.db_pool, endpoint)
    return {"ok": True}
