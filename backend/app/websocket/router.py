"""WebSocket endpoint for real-time mail notifications.

Architecture:
- Each connected client subscribes to a Redis pub/sub channel (user-specific)
- A background task polls IMAP every 45s per user and publishes changes to Redis
- Redis pub/sub broadcasts to all workers (Uvicorn runs 4 workers)
- Heartbeat ping/pong every 30s to detect stale connections
- Auth via access_token cookie (same as REST API)

This module is purely additive — it does NOT modify any existing endpoint or service.
"""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.auth.jwt import decode_access_token
from app.core.session import decrypt_password

logger = logging.getLogger("websocket")

router = APIRouter()

# Per-worker connection registry: username -> set of WebSocket connections
_connections: Dict[str, Set[WebSocket]] = {}

# Per-worker IMAP poll tasks: username -> asyncio.Task
_poll_tasks: Dict[str, asyncio.Task] = {}

# Track last known INBOX unseen count per user (avoid duplicate notifications)
_last_unseen: Dict[str, int] = {}


def _authenticate_ws(websocket: WebSocket) -> str | None:
    """Extract and validate username from access_token cookie.
    Returns username or None if invalid."""
    token = websocket.cookies.get("access_token")
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    return payload.get("sub")


async def _ultimo_sin_leer(imap) -> int | None:
    """UID del correo sin leer más reciente de INBOX. Si algo falla, None: el aviso
    sale igual, apuntando a la bandeja."""
    try:
        await imap.select("INBOX")
        r = await imap.uid_search("UNSEEN")
        if getattr(r, "result", "") != "OK":
            return None
        for linea in r.lines or []:
            texto = (
                linea.decode("utf-8", "replace")
                if isinstance(linea, bytes)
                else str(linea)
            )
            uids = [u for u in texto.split() if u.isdigit()]
            if uids:
                return int(uids[-1])
        return None
    except Exception:
        return None


async def aviso_correo_al_canal(
    username: str, nuevos: int, sin_leer: int, uid: int | None = None
) -> None:
    """Avisa al canal de notificaciones (lo que ve la app de escritorio) que llegó
    correo. tipo='correo' y url del webmail; nunca interrumpe la operación."""
    import os

    try:
        secreto = os.getenv("NOTIF_SECRET", "")
        if not secreto or not username:
            return
        texto = (
            "Tienes 1 correo nuevo"
            if nuevos == 1
            else "Tienes %d correos nuevos" % nuevos
        )
        if sin_leer and sin_leer != nuevos:
            texto += " (%d sin leer)" % sin_leer
        import httpx

        async with httpx.AsyncClient(timeout=4) as c:
            await c.post(
                "https://mail.maquita.org/api/chat/notificaciones",
                headers={"X-Notif-Secret": secreto},
                json={
                    "correos": [username],
                    "tipo": "correo",
                    "titulo": "Correo nuevo",
                    "texto": texto,
                    "url": (
                        "https://mail.maquita.org/webmail/?folder=INBOX&uid=%d" % uid
                        if uid
                        else "https://mail.maquita.org/webmail/"
                    ),
                    "origen": "correo",
                },
            )
    except Exception:
        pass


async def _send_safe(ws: WebSocket, data: dict) -> bool:
    """Send JSON to a WebSocket, return False if connection is dead."""
    try:
        await ws.send_json(data)
        return True
    except Exception:
        return False


async def _broadcast_to_user(username: str, data: dict):
    """Send a message to all local connections of a user."""
    conns = _connections.get(username, set())
    dead = set()
    for ws in conns:
        if not await _send_safe(ws, data):
            dead.add(ws)
    # Clean up dead connections
    if dead:
        _connections[username] = conns - dead


async def _redis_subscriber(app_state):
    """Listen to Redis pub/sub and broadcast to local WebSocket connections.
    Runs once per worker. Reconnects on failure."""
    while True:
        try:
            redis = app_state.redis
            pubsub = redis.pubsub()
            await pubsub.psubscribe("ws:user:*")
            logger.info("Redis subscriber started")

            async for message in pubsub.listen():
                if message["type"] not in ("pmessage",):
                    continue
                try:
                    channel = message["channel"]
                    # channel = "ws:user:username@domain.com"
                    username = (
                        channel.split("ws:user:", 1)[1]
                        if "ws:user:" in channel
                        else None
                    )
                    if not username or username not in _connections:
                        continue
                    data = json.loads(message["data"])
                    await _broadcast_to_user(username, data)
                except Exception as exc:
                    logger.debug(f"Redis message parse error: {exc}")

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning(f"Redis subscriber error, reconnecting in 5s: {exc}")
            await asyncio.sleep(5)


async def _poll_user_inbox(username: str, app_state):
    """Poll IMAP for new messages for a specific user every 45s.
    Publishes to Redis when unseen count changes."""
    while True:
        try:
            await asyncio.sleep(45)

            # Check user still has active connections on this worker
            if username not in _connections or not _connections[username]:
                break

            # Get cached password from Redis and decrypt
            redis = app_state.redis
            raw_pass = await redis.get(f"imap_pass:{username}")
            if not raw_pass:
                # Session expired — notify client
                await redis.publish(
                    f"ws:user:{username}",
                    json.dumps(
                        {
                            "type": "session_expired",
                        }
                    ),
                )
                break

            try:
                password = decrypt_password(raw_pass)
            except Exception:
                password = raw_pass  # fallback for unencrypted legacy values

            # Quick IMAP check: just get INBOX unseen count
            from app.mail.clients.imap_client import get_imap_connection

            imap = None
            try:
                imap = await asyncio.wait_for(
                    get_imap_connection(username, password),
                    timeout=10,
                )
                resp = await asyncio.wait_for(
                    imap.status("INBOX", "(UNSEEN MESSAGES)"),
                    timeout=10,
                )

                unseen = 0
                total = 0
                if resp.result == "OK":
                    for line in resp.lines:
                        text = (
                            line.decode("utf-8", "replace")
                            if isinstance(line, bytes)
                            else str(line)
                        )
                        import re

                        m_unseen = re.search(r"UNSEEN\s+(\d+)", text)
                        m_total = re.search(r"MESSAGES\s+(\d+)", text)
                        if m_unseen:
                            unseen = int(m_unseen.group(1))
                        if m_total:
                            total = int(m_total.group(1))

                prev = _last_unseen.get(username, -1)
                if prev != -1 and unseen > prev:
                    # New mail arrived
                    await redis.publish(
                        f"ws:user:{username}",
                        json.dumps(
                            {
                                "type": "new_mail",
                                "folder": "INBOX",
                                "unseen": unseen,
                                "total": total,
                                "delta": unseen - prev,
                            }
                        ),
                    )
                    # Aviso al canal del cliente Windows (tipo «correo»)
                    _uid_nuevo = await _ultimo_sin_leer(imap)
                    await aviso_correo_al_canal(
                        username, unseen - prev, unseen, _uid_nuevo
                    )
                    # Web push (#17): notifica al navegador aunque la PWA este cerrada.
                    try:
                        from app.push import service as _push

                        _n = unseen - prev
                        _txt = (
                            "Tienes 1 correo nuevo"
                            if _n == 1
                            else "Tienes %d correos nuevos" % _n
                        )
                        _url = (
                            ("/webmail/?folder=INBOX&uid=%d" % _uid_nuevo)
                            if _uid_nuevo
                            else "/webmail/"
                        )
                        await _push.enviar_a_usuario(
                            app_state.db_pool, username, "Correo nuevo", _txt, _url
                        )
                    except Exception:
                        pass
                elif unseen != prev:
                    # Unseen count changed (read/deleted externally)
                    await redis.publish(
                        f"ws:user:{username}",
                        json.dumps(
                            {
                                "type": "folder_update",
                                "folder": "INBOX",
                                "unseen": unseen,
                                "total": total,
                            }
                        ),
                    )

                _last_unseen[username] = unseen

            finally:
                if imap:
                    try:
                        await imap.logout()
                    except Exception:
                        pass

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug(f"Poll error for {username}: {exc}")
            await asyncio.sleep(45)

    # Cleanup
    _poll_tasks.pop(username, None)
    _last_unseen.pop(username, None)


def _start_poll_task(username: str, app_state):
    """Start a poll task for a user if one doesn't exist on this worker."""
    if username not in _poll_tasks or _poll_tasks[username].done():
        task = asyncio.create_task(_poll_user_inbox(username, app_state))
        _poll_tasks[username] = task


@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time notifications.

    Protocol:
    - Client connects with access_token cookie (same as REST API)
    - Server sends {"type": "connected"} on success
    - Server sends {"type": "ping"} every 30s, client should respond {"type": "pong"}
    - Server sends {"type": "new_mail", ...} when new mail arrives
    - Server sends {"type": "folder_update", ...} when folder counts change
    - Server sends {"type": "session_expired"} when IMAP session lost
    - Client can send {"type": "pong"} in response to pings
    """
    # Authenticate before accepting
    username = _authenticate_ws(websocket)
    if not username:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    # Register connection
    if username not in _connections:
        _connections[username] = set()
    _connections[username].add(websocket)

    # Start IMAP poll task for this user if needed
    _start_poll_task(username, websocket.app.state)

    # Send connected confirmation
    await _send_safe(websocket, {"type": "connected", "username": username})
    logger.info(
        f"WS connected: {username} (total: {len(_connections.get(username, set()))})"
    )

    # Heartbeat + receive loop
    try:
        last_pong = asyncio.get_event_loop().time()

        async def heartbeat():
            nonlocal last_pong
            while True:
                await asyncio.sleep(30)
                if asyncio.get_event_loop().time() - last_pong > 90:
                    # No pong in 90s — client is dead
                    logger.info(f"WS timeout: {username}")
                    await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                    return
                await _send_safe(websocket, {"type": "ping"})

        heartbeat_task = asyncio.create_task(heartbeat())

        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "")
                if msg_type == "pong":
                    last_pong = asyncio.get_event_loop().time()
                elif msg_type == "refresh":
                    # Client requests immediate check
                    _start_poll_task(username, websocket.app.state)
        except WebSocketDisconnect:
            pass
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    finally:
        # Unregister connection
        conns = _connections.get(username, set())
        conns.discard(websocket)
        if not conns:
            _connections.pop(username, None)
            # Cancel poll task if no more connections
            task = _poll_tasks.pop(username, None)
            if task and not task.done():
                task.cancel()
            _last_unseen.pop(username, None)
        logger.info(f"WS disconnected: {username}")


async def start_redis_subscriber(app_state):
    """Start the Redis subscriber. Called from main.py lifespan."""
    return asyncio.create_task(_redis_subscriber(app_state))
