"""User presence — online/busy/away/offline status via Redis + WebSocket."""

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/presence", tags=["presence"])

PREFIX = "presence:"
CHANNEL = "presence_updates"
TTL = 120


class StatusUpdate(BaseModel):
    status: str = "online"


def _redis(request: Request):
    return request.app.state.redis


@router.put("/status")
async def set_status(
    body: StatusUpdate, request: Request, user: str = Depends(get_current_user)
):
    r = _redis(request)
    data = json.dumps(
        {"user": user, "status": body.status, "ts": datetime.utcnow().isoformat()}
    )
    await r.set(f"{PREFIX}{user}", data, ex=TTL)
    await r.publish(CHANNEL, data)
    return {"ok": True}


@router.post("/heartbeat")
async def heartbeat(request: Request, user: str = Depends(get_current_user)):
    r = _redis(request)
    key = f"{PREFIX}{user}"
    existing = await r.get(key)
    if existing:
        await r.expire(key, TTL)
    else:
        data = json.dumps(
            {"user": user, "status": "online", "ts": datetime.utcnow().isoformat()}
        )
        await r.set(key, data, ex=TTL)
        await r.publish(CHANNEL, data)
    return {"ok": True}


@router.get("/users")
async def get_all_presence(request: Request, user: str = Depends(get_current_user)):
    """Return only the current user's own presence status for privacy."""
    r = _redis(request)
    data = await r.get(f"{PREFIX}{user}")
    if data:
        return [json.loads(data)]
    return [{"user": user, "status": "offline", "ts": None}]


@router.get("/user/{email}")
async def get_user_presence(
    email: str, request: Request, user: str = Depends(get_current_user)
):
    r = _redis(request)
    data = await r.get(f"{PREFIX}{email}")
    if data:
        return json.loads(data)
    return {"user": email, "status": "offline", "ts": None}


@router.websocket("/ws")
async def presence_ws(websocket: WebSocket):
    # Autenticar via cookie antes de aceptar la conexión
    from app.auth.jwt import decode_access_token

    token = websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=4001, reason="No autenticado")
        return
    try:
        username = decode_access_token(token)
        if not username:
            await websocket.close(code=4001, reason="Token invalido")
            return
    except Exception:
        await websocket.close(code=4001, reason="Token invalido")
        return

    await websocket.accept()
    logger.info("Presence WS conectado: %s", username)
    r = websocket.app.state.redis
    pubsub = r.pubsub()
    await pubsub.subscribe(CHANNEL)
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg["type"] == "message":
                await websocket.send_text(
                    msg["data"]
                    if isinstance(msg["data"], str)
                    else msg["data"].decode()
                )
            await asyncio.sleep(0.1)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        await pubsub.unsubscribe(CHANNEL)
