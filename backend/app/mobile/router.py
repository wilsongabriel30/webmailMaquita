"""Mobile API — device registration and configuration endpoints."""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config import get_settings

logger = logging.getLogger("mobile")

router = APIRouter(prefix="/api/mobile", tags=["mobile"])


class DeviceRegister(BaseModel):
    device_id: str
    device_name: Optional[str] = None
    platform: Optional[str] = None  # 'ios', 'android'
    push_token: Optional[str] = None


@router.get("/config")
async def mobile_config(request: Request):
    """Return server configuration for mobile apps."""
    s = get_settings()
    return {
        "imap": {"host": s.cookie_domain, "port": 993, "ssl": True},
        "smtp": {"host": s.cookie_domain, "port": 465, "ssl": True},
        "caldav": {"url": f"https://{s.cookie_domain}/radicale/"},
        "carddav": {"url": f"https://{s.cookie_domain}/radicale/"},
        "activesync": {"url": f"https://{s.cookie_domain}/Microsoft-Server-ActiveSync"},
        "webmail": {"url": f"https://{s.cookie_domain}"},
        "api_version": "1.0",
        "features": [
            "smart-reply",
            "priority-inbox",
            "calendar",
            "contacts",
            "delegation",
            "attachment-scan",
        ],
    }


@router.post("/register-device")
async def register_device(request: Request, body: DeviceRegister):
    """Register a mobile device for push notifications."""
    user = await get_current_user(request)
    db = request.app.state.db_pool

    # Upsert
    await db.execute(
        """INSERT INTO mobile_devices (user_email, device_id, device_name, platform, push_token, last_sync)
           VALUES ($1, $2, $3, $4, $5, NOW())
           ON CONFLICT (device_id) DO UPDATE SET
               device_name = EXCLUDED.device_name,
               platform = EXCLUDED.platform,
               push_token = EXCLUDED.push_token,
               last_sync = NOW(),
               is_active = true""",
        user,
        body.device_id,
        body.device_name,
        body.platform,
        body.push_token,
    )

    return {"status": "registered", "device_id": body.device_id}


@router.delete("/unregister-device")
async def unregister_device(request: Request, device_id: str):
    """Deactivate a mobile device."""
    user = await get_current_user(request)
    db = request.app.state.db_pool

    result = await db.execute(
        "UPDATE mobile_devices SET is_active = false WHERE device_id = $1 AND user_email = $2",
        device_id,
        user,
    )

    return {"status": "unregistered", "device_id": device_id}


@router.get("/sync-status")
async def sync_status(request: Request):
    """Get sync status for all devices of the current user."""
    user = await get_current_user(request)
    db = request.app.state.db_pool

    devices = await db.fetch(
        """SELECT device_id, device_name, platform, last_sync, is_active, created_at
           FROM mobile_devices
           WHERE user_email = $1
           ORDER BY last_sync DESC NULLS LAST""",
        user,
    )

    return {
        "user": user,
        "devices": [
            {
                "device_id": d["device_id"],
                "device_name": d["device_name"],
                "platform": d["platform"],
                "last_sync": d["last_sync"].isoformat() if d["last_sync"] else None,
                "is_active": d["is_active"],
                "created_at": d["created_at"].isoformat() if d["created_at"] else None,
            }
            for d in devices
        ],
    }


@router.get("/devices")
async def list_devices(request: Request):
    """List all active devices for the current user."""
    user = await get_current_user(request)
    db = request.app.state.db_pool

    devices = await db.fetch(
        """SELECT device_id, device_name, platform, last_sync, created_at
           FROM mobile_devices
           WHERE user_email = $1 AND is_active = true
           ORDER BY last_sync DESC NULLS LAST""",
        user,
    )

    return {
        "count": len(devices),
        "devices": [
            {
                "device_id": d["device_id"],
                "device_name": d["device_name"],
                "platform": d["platform"],
                "last_sync": d["last_sync"].isoformat() if d["last_sync"] else None,
                "created_at": d["created_at"].isoformat() if d["created_at"] else None,
            }
            for d in devices
        ],
    }
