"""Puntos de entrada públicos (sin sesión) de la recuperación entre servidores."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.dispositivos.seguridad import ip_cliente, limitar
from app.federacion import recuperacion_protocolo as protocolo
from app.federacion import recuperacion_servidor
from app.mail.services import plazo_recuperacion

router = APIRouter(prefix=protocolo.RUTA_BASE, tags=["federacion"])


def _exigir_activo() -> None:
    if not protocolo.activo():
        raise HTTPException(status_code=404, detail="No disponible")


@router.get("")
async def capacidades():
    """Otro servidor pregunta si aquí se admite la recuperación entre servidores."""
    _exigir_activo()
    return {
        "version": protocolo.VERSION,
        "activo": True,
        "plazo_minutos": plazo_recuperacion.minutos_maximos(),
    }


@router.post("/solicitar")
async def solicitar(request: Request, body: protocolo.Solicitud):
    """El servidor de un remitente pide retirar un correo de un buzón de este servidor."""
    _exigir_activo()
    ip = ip_cliente(request)
    await limitar(request, f"fedsol:{ip}", 30, 60)
    return await recuperacion_servidor.atender(request, body, ip or None)


@router.post("/confirmar")
async def confirmar(request: Request, body: protocolo.Solicitud):
    """El servidor de un destinatario pregunta si esta solicitud la emitió este servidor."""
    _exigir_activo()
    await limitar(request, f"fedconf:{ip_cliente(request)}", 120, 60)
    return {"confirmado": await protocolo.confirmar(request.app.state.redis, body)}
