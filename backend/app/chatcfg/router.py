"""Configuración de la integración del Chat (panel de control del webmail).

Permite al administrador activar/desactivar el chat y parametrizar la URL del
servidor de chat (útil para quien adopte el proyecto y conecte su propia
instancia/docker). La lectura pública (GET /api/chat-config) solo expone datos NO
sensibles (activado + URL a embeber); el secreto JWT vive en el chat-service, no
aquí.
"""
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel

from app.auth.dependencies import require_admin

router = APIRouter(tags=["chat-config"])

_DEFAULTS = {"enabled": "1", "embed_url": "/chat/?embed=1"}


async def _ensure(db):
    await db.execute(
        "CREATE TABLE IF NOT EXISTS chat_settings (key text PRIMARY KEY, value text)"
    )


async def _read(db) -> dict:
    await _ensure(db)
    rows = await db.fetch("SELECT key, value FROM chat_settings")
    data = dict(_DEFAULTS)
    data.update({r["key"]: r["value"] for r in rows})
    return data


def _to_public(data: dict) -> dict:
    return {
        "enabled": data.get("enabled", "1") not in ("0", "false", "False", ""),
        "embed_url": data.get("embed_url") or _DEFAULTS["embed_url"],
    }


class ChatConfigIn(BaseModel):
    enabled: bool
    embed_url: str | None = None


@router.get("/api/chat-config")
async def get_chat_config_public(request: Request):
    """Lectura pública para el frontend (solo activado + URL a embeber)."""
    try:
        data = await _read(request.app.state.db_pool)
    except Exception:
        # Ante cualquier fallo, no romper el correo: chat activado por defecto.
        return _to_public({})
    return _to_public(data)


@router.get("/api/admin/chat-config")
async def get_chat_config_admin(request: Request, admin: str = Depends(require_admin)):
    data = await _read(request.app.state.db_pool)
    return _to_public(data)


@router.put("/api/admin/chat-config")
async def put_chat_config(body: ChatConfigIn, request: Request, admin: str = Depends(require_admin)):
    db = request.app.state.db_pool
    await _ensure(db)
    url = (body.embed_url or "").strip() or _DEFAULTS["embed_url"]
    pairs = {"enabled": "1" if body.enabled else "0", "embed_url": url}
    for k, v in pairs.items():
        await db.execute(
            "INSERT INTO chat_settings(key,value) VALUES($1,$2) "
            "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
            k, v,
        )
    return _to_public(await _read(db))
