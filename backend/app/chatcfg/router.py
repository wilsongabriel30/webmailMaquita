"""Configuracion de la integracion del Chat (panel de control del webmail).

Permite al administrador activar/desactivar el chat, parametrizar la URL del
servidor de chat, y definir el AISLAMIENTO POR DOMINIO (multi-empresa): que
dominios pueden chatear entre si y cuales quedan aislados. Solo afecta al CHAT;
el correo (email) entre dominios NO se toca.

La lectura publica (GET /api/chat-config) expone datos NO sensibles; el servicio
de chat la lee para aplicar el aislamiento.
"""
import json
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from typing import List, Optional

from app.auth.dependencies import require_admin

router = APIRouter(tags=["chat-config"])

_DEFAULTS = {
    "enabled": "1",
    "embed_url": "/chat/?embed=1",
    "domain_isolation": "0",
    "domain_groups": "[]",
}


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


def _parse_groups(raw):
    """Normaliza a lista de listas de dominios en minuscula, sin vacios/duplicados."""
    try:
        groups = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except Exception:
        groups = []
    out = []
    for g in groups:
        if not isinstance(g, list):
            continue
        doms = []
        for d in g:
            d = (d or "").strip().lower().lstrip("@")
            if d and d not in doms:
                doms.append(d)
        if doms:
            out.append(doms)
    return out


def _to_public(data: dict) -> dict:
    return {
        "enabled": data.get("enabled", "1") not in ("0", "false", "False", ""),
        "embed_url": data.get("embed_url") or _DEFAULTS["embed_url"],
        "domain_isolation": data.get("domain_isolation", "0") not in ("0", "false", "False", ""),
        "domain_groups": _parse_groups(data.get("domain_groups", "[]")),
    }


class ChatConfigIn(BaseModel):
    enabled: bool
    embed_url: Optional[str] = None
    domain_isolation: bool = False
    domain_groups: Optional[List[List[str]]] = None


@router.get("/api/chat-config")
async def get_chat_config_public(request: Request):
    try:
        data = await _read(request.app.state.db_pool)
    except Exception:
        return _to_public({})
    return _to_public(data)


@router.get("/api/admin/chat-config")
async def get_chat_config_admin(request: Request, admin: str = Depends(require_admin)):
    return _to_public(await _read(request.app.state.db_pool))


@router.put("/api/admin/chat-config")
async def put_chat_config(body: ChatConfigIn, request: Request, admin: str = Depends(require_admin)):
    db = request.app.state.db_pool
    await _ensure(db)
    url = (body.embed_url or "").strip() or _DEFAULTS["embed_url"]
    groups = _parse_groups(body.domain_groups or [])
    pairs = {
        "enabled": "1" if body.enabled else "0",
        "embed_url": url,
        "domain_isolation": "1" if body.domain_isolation else "0",
        "domain_groups": json.dumps(groups),
    }
    for k, v in pairs.items():
        await db.execute(
            "INSERT INTO chat_settings(key,value) VALUES($1,$2) "
            "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
            k, v,
        )
    return _to_public(await _read(db))
