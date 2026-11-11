"""Puntos de entrada públicos (sin sesión) de las reacciones entre servidores."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.dispositivos.seguridad import ip_cliente, limitar
from app.federacion import reacciones_protocolo as protocolo
from app.federacion import reacciones_servidor

router = APIRouter(prefix=protocolo.RUTA_BASE, tags=["federacion"])


def _exigir_activo() -> None:
    if not protocolo.activo():
        raise HTTPException(status_code=404, detail="No disponible")


@router.get("")
async def capacidades():
    _exigir_activo()
    return {"version": protocolo.VERSION, "activo": True}


@router.post("/avisar")
async def avisar(request: Request, body: protocolo.Aviso):
    """Otro servidor avisa de que una persona suya reaccionó a un correo que también está aquí."""
    _exigir_activo()
    await limitar(request, f"fedreac:{ip_cliente(request)}", 120, 60)
    return await reacciones_servidor.atender(request, body)


@router.post("/confirmar")
async def confirmar(request: Request, body: protocolo.Aviso):
    """Otro servidor pregunta si este aviso lo emitió este servidor."""
    _exigir_activo()
    await limitar(request, f"fedreacconf:{ip_cliente(request)}", 240, 60)
    return {"confirmado": await protocolo.confirmar(request.app.state.redis, body)}
