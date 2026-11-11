"""El servidor de correo avisa de que hay un mensaje en camino para unos buzones (11/11/2026).

Lo llama el filtro de contenido de Postfix justo después de reinyectar el mensaje, desde la propia
máquina. Solo se acepta desde el bucle local y sin pasar por nginx (que añade `X-Real-IP`): desde
fuera responde 404. No lleva datos del correo: solo las direcciones a las que hay que despertarles
el sondeo (`app/websocket/despertador.py`).
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.websocket import despertador

router = APIRouter(prefix="/api/interno", tags=["interno"])

_CORREO = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_LOCALES = {"127.0.0.1", "::1"}


class EnCamino(BaseModel):
    destinatarios: list[str] = Field(default_factory=list, max_length=200)


def es_llamada_local(request: Request) -> bool:
    if request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for"):
        return False
    return bool(request.client) and request.client.host in _LOCALES


@router.post("/correo-en-camino")
async def correo_en_camino(body: EnCamino, request: Request):
    if not es_llamada_local(request):
        raise HTTPException(status_code=404, detail="Not Found")
    avisados = 0
    for direccion in {d.strip().lower() for d in body.destinatarios}:
        if _CORREO.match(direccion):
            await request.app.state.redis.publish(despertador.CANAL + direccion, "1")
            avisados += 1
    return {"avisados": avisados}
