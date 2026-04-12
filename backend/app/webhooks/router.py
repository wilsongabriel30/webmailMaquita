"""Webhooks management router."""
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field, HttpUrl

from app.auth.dependencies import get_current_user

logger = logging.getLogger("webhooks")

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

VALID_EVENTS = [
    "mail.received", "mail.sent",
    "contact.created", "contact.updated",
    "calendar.event.created", "calendar.event.updated",
]

# ---------- Pydantic models ----------

class WebhookCreate(BaseModel):
    url: str = Field(..., min_length=10)
    events: list[str] = Field(..., min_length=1)

class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    events: Optional[list[str]] = None
    is_active: Optional[bool] = None

class WebhookOut(BaseModel):
    id: int
    url: str
    secret: str
    events: list[str]
    is_active: bool
    created_at: str
    last_triggered_at: Optional[str] = None
    failure_count: int

# ---------- Helpers ----------

# _get_user_id removed in Fase 2 cleanup - using user_email directly

def _row_to_dict(row) -> dict:
    d = dict(row)
    for k in ("created_at", "last_triggered_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
        elif k == "last_triggered_at":
            d[k] = None
        else:
            d[k] = ""
    return d

# ---------- CRUD endpoints ----------

@router.post("", status_code=201)
async def create_webhook(body: WebhookCreate, request: Request, username: str = Depends(get_current_user)):
    for ev in body.events:
        if ev not in VALID_EVENTS:
            raise HTTPException(400, detail=f"Invalid event: {ev}")
    db = request.app.state.db_pool
    secret = secrets.token_urlsafe(32)
    row = await db.fetchrow(
        """INSERT INTO webhooks (user_email, url, secret, events)
           VALUES ($1, $2, $3, $4) RETURNING *""",
        username, str(body.url), secret, body.events,
    )
    return _row_to_dict(row)

@router.get("")
async def list_webhooks(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    rows = await db.fetch("SELECT * FROM webhooks WHERE user_email = $1 ORDER BY id", username)
    return [_row_to_dict(r) for r in rows]

@router.get("/{webhook_id}")
async def get_webhook(webhook_id: int, request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    row = await db.fetchrow("SELECT * FROM webhooks WHERE id = $1 AND user_email = $2", webhook_id, username)
    if not row:
        raise HTTPException(404, "Webhook not found")
    return _row_to_dict(row)

@router.put("/{webhook_id}")
async def update_webhook(webhook_id: int, body: WebhookUpdate, request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    row = await db.fetchrow("SELECT * FROM webhooks WHERE id = $1 AND user_email = $2", webhook_id, username)
    if not row:
        raise HTTPException(404, "Webhook not found")
    updates = {}
    if body.url is not None:
        updates["url"] = body.url
    if body.events is not None:
        for ev in body.events:
            if ev not in VALID_EVENTS:
                raise HTTPException(400, detail=f"Invalid event: {ev}")
        updates["events"] = body.events
    if body.is_active is not None:
        updates["is_active"] = body.is_active
        if body.is_active:
            updates["failure_count"] = 0
    if not updates:
        return _row_to_dict(row)
    set_parts = []
    values = []
    for i, (k, v) in enumerate(updates.items(), 1):
        set_parts.append(f"{k} = ${i}")
        values.append(v)
    values.extend([webhook_id, username])
    query = f"UPDATE webhooks SET {', '.join(set_parts)} WHERE id = ${len(values)-1} AND user_email = ${len(values)} RETURNING *"
    updated = await db.fetchrow(query, *values)
    return _row_to_dict(updated)

@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(webhook_id: int, request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    result = await db.execute("DELETE FROM webhooks WHERE id = $1 AND user_email = $2", webhook_id, username)
    if result == "DELETE 0":
        raise HTTPException(404, "Webhook not found")
    return None

@router.get("/{webhook_id}/logs")
async def get_webhook_logs(webhook_id: int, request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    row = await db.fetchrow("SELECT id FROM webhooks WHERE id = $1 AND user_email = $2", webhook_id, username)
    if not row:
        raise HTTPException(404, "Webhook not found")
    logs = await db.fetch(
        "SELECT * FROM webhook_logs WHERE webhook_id = $1 ORDER BY created_at DESC LIMIT 50", webhook_id
    )
    result = []
    for l in logs:
        d = dict(l)
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        if d.get("payload"):
            import json as _json
            d["payload"] = _json.loads(d["payload"]) if isinstance(d["payload"], str) else d["payload"]
        result.append(d)
    return result

@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: int, request: Request, bg: BackgroundTasks, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    row = await db.fetchrow("SELECT * FROM webhooks WHERE id = $1 AND user_email = $2", webhook_id, username)
    if not row:
        raise HTTPException(404, "Webhook not found")
    test_payload = {"event": "webhook.test", "data": {"message": "This is a test webhook delivery"}, "timestamp": datetime.now(timezone.utc).isoformat()}
    bg.add_task(_fire_webhook, db, dict(row), "webhook.test", test_payload)
    return {"status": "test event queued"}

# ---------- Trigger function ----------

async def _fire_webhook(db, webhook: dict, event: str, payload: dict):
    """Send POST to webhook URL with HMAC signature."""
    body_bytes = json.dumps(payload, default=str).encode()
    signature = hmac.new(webhook["secret"].encode(), body_bytes, hashlib.sha256).hexdigest()
    resp_status = None
    resp_body = None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                webhook["url"],
                content=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                    "X-Webhook-Event": event,
                },
            )
            resp_status = resp.status_code
            resp_body = resp.text[:2000]
    except Exception as e:
        resp_status = 0
        resp_body = str(e)[:2000]

    # Log
    await db.execute(
        """INSERT INTO webhook_logs (webhook_id, event, payload, response_status, response_body)
           VALUES ($1, $2, $3::jsonb, $4, $5)""",
        webhook["id"], event, json.dumps(payload, default=str), resp_status, resp_body,
    )

    # Update last_triggered_at & failure tracking
    if resp_status and 200 <= resp_status < 300:
        await db.execute(
            "UPDATE webhooks SET last_triggered_at = NOW(), failure_count = 0 WHERE id = $1",
            webhook["id"],
        )
    else:
        new_count = webhook.get("failure_count", 0) + 1
        if new_count >= 5:
            await db.execute(
                "UPDATE webhooks SET failure_count = $1, is_active = false WHERE id = $2",
                new_count, webhook["id"],
            )
            logger.warning("Webhook %s disabled after %d failures", webhook["id"], new_count)
        else:
            await db.execute(
                "UPDATE webhooks SET failure_count = $1 WHERE id = $2",
                new_count, webhook["id"],
            )

async def trigger_webhook(event: str, payload: dict, user_email: str, db_pool):
    """Public helper: find active webhooks for user+event and fire them."""
    rows = await db_pool.fetch(
        "SELECT * FROM webhooks WHERE user_email = $1 AND is_active = true AND $2 = ANY(events)",
        user_email, event,
    )
    for row in rows:
        try:
            await _fire_webhook(db_pool, dict(row), event, payload)
        except Exception:
            logger.exception("Error triggering webhook %s", row["id"])
