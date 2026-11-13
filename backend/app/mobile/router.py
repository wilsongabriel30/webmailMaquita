"""Mobile API — device registration and configuration endpoints."""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app import organizacion
from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.mobile import avisos_correo
from app.portales import direcciones

logger = logging.getLogger("mobile")

router = APIRouter(prefix="/api/mobile", tags=["mobile"])


class DeviceRegister(BaseModel):
    device_id: str
    device_name: Optional[str] = None
    platform: Optional[str] = None  # 'ios', 'android'
    push_token: Optional[str] = None
    avisos: Optional[bool] = (
        None  # False: este teléfono no quiere avisos de correo al instante
    )


@router.get("/config")
async def mobile_config(request: Request):
    """Configuración de servidores para las aplicaciones móviles.

    Con `?correo=` se entrega el servidor de la empresa de esa cuenta. Sin él, el del portal
    por el que llega la petición; y si no es un portal, el general.
    """
    db = getattr(request.app.state, "db_pool", None)
    correo = (request.query_params.get("correo") or "").strip().lower()
    if "@" in correo:
        servidor = await direcciones.servidor_de_cuenta(db, correo)
    else:
        servidor = organizacion.servidor(await direcciones.url_de_peticion(db, request))
    return {
        "imap": {"host": servidor, "port": 993, "ssl": True},
        "smtp": {"host": servidor, "port": 465, "ssl": True},
        "caldav": {"url": f"https://{servidor}/radicale/"},
        "carddav": {"url": f"https://{servidor}/radicale/"},
        "activesync": {"url": f"https://{servidor}/Microsoft-Server-ActiveSync"},
        "webmail": {"url": f"https://{servidor}"},
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
    """Registra el teléfono y le entrega su canal de avisos de correo (AM-01, avisos_correo.py).

    Exige sesión. El teléfono queda ligado a esa sesión: si se cierra o caduca, deja de recibir avisos
    hasta que vuelva a registrarse con una sesión nueva. El tema asignado se conserva entre registros.
    Un teléfono con varias cuentas se registra una vez por cuenta y recibe un tema por cada una.
    """
    user = await get_current_user(request)
    db = request.app.state.db_pool
    device_id = (body.device_id or "").strip()
    if not 8 <= len(device_id) <= 128:
        raise HTTPException(
            status_code=422, detail="device_id debe tener entre 8 y 128 caracteres"
        )
    fila = await db.fetchrow(
        """INSERT INTO mobile_devices
               (user_email, device_id, device_name, platform, push_token, last_sync, push_topic, sid, avisos)
           VALUES ($1, $2, $3, $4, $5, NOW(), $6, $7, COALESCE($8, true))
           ON CONFLICT (device_id, user_email) DO UPDATE SET
               device_name = EXCLUDED.device_name,
               platform = EXCLUDED.platform,
               push_token = EXCLUDED.push_token,
               last_sync = NOW(),
               is_active = true,
               sid = EXCLUDED.sid,
               avisos = COALESCE($8, mobile_devices.avisos),
               push_topic = COALESCE(mobile_devices.push_topic, EXCLUDED.push_topic)
           RETURNING push_topic, avisos""",
        user.lower(),
        device_id,
        (body.device_name or "")[:120] or None,
        (body.platform or "")[:20] or None,
        body.push_token,
        avisos_correo.nuevo_tema(),
        getattr(request.state, "sid", None),
        body.avisos,
    )
    return {
        "status": "registered",
        "device_id": device_id,
        "avisos": fila["avisos"],
        "push": avisos_correo.bloque_push(
            request.headers.get("host", ""), fila["push_topic"], fila["avisos"]
        ),
    }


@router.delete("/unregister-device")
async def unregister_device(request: Request, device_id: str):
    """Da de baja el teléfono: deja de recibir avisos y su tema se descarta."""
    user = await get_current_user(request)
    db = request.app.state.db_pool

    await db.execute(
        "UPDATE mobile_devices SET is_active = false, push_topic = NULL, sid = NULL "
        "WHERE device_id = $1 AND lower(user_email) = lower($2)",
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
