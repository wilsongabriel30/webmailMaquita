"""Consulta de sesión para otros servicios (el chat, F-03).

`GET /api/auth/sesion-servicio?user=…&sid=…` responde si esa sesión del correo sigue viva
y cuál es la generación vigente del usuario. Se autentica con el secreto compartido de
servicios (`X-Notif-Secret`, el mismo que usan las notificaciones), comparado en tiempo
constante, y con límite de peticiones por IP: quien lo tuviera no puede usarlo para
enumerar sesiones a gran velocidad.
"""

import hmac
import logging

from fastapi import APIRouter, HTTPException, Request

from app.auth.sesiones import av_actual
from app.tareas.avisos import _secreto as _secreto_servicios

router = APIRouter(prefix="/api/auth", tags=["auth-servicio"])
security_log = logging.getLogger("security")
LIMITE_POR_MIN = 300


@router.get("/sesion-servicio")
async def sesion_servicio(request: Request, user: str, sid: str):
    secreto = _secreto_servicios()
    recibido = request.headers.get("x-notif-secret", "")
    if not secreto or not hmac.compare_digest(secreto, recibido):
        raise HTTPException(403, "No autorizado")

    redis = request.app.state.redis
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "?")
    try:
        clave = f"rl:sesion-servicio:{ip}"
        n = await redis.incr(clave)
        if n == 1:
            await redis.expire(clave, 60)
        if n > LIMITE_POR_MIN:
            raise HTTPException(429, "Demasiadas peticiones")
    except HTTPException:
        raise
    except Exception as exc:
        security_log.error("RATE_LIMIT_SIN_REDIS tier=sesion-servicio error=%s", str(exc)[:120])
        raise HTTPException(503, "No disponible")

    user = (user or "").strip().lower()[:255]
    sid = (sid or "").strip()[:64]
    if not user or not sid:
        raise HTTPException(400, "Faltan user o sid")
    valida = bool(await redis.exists(f"sess:{user}:{sid}"))
    av = await av_actual(request.app.state.db_pool, redis, user)
    return {"valida": valida, "av": av}
