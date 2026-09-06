"""Configuracion de la integracion del Chat (panel de control del webmail).

Permite al administrador activar/desactivar el chat, parametrizar la URL del
servidor de chat, y definir el AISLAMIENTO POR DOMINIO (multi-empresa): que
dominios pueden chatear entre si y cuales quedan aislados. Solo afecta al CHAT;
el correo (email) entre dominios NO se toca.

La lectura publica (GET /api/chat-config) expone datos NO sensibles; el servicio
de chat la lee para aplicar el aislamiento.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, require_admin

router = APIRouter(tags=["chat-config"])

# --- Vale de entrada al chat en su propio origen -------------------------------
# El chat dejo de compartir origen con el correo, asi que su cookie ya no viaja.
# El correo emite un vale corto y de un solo uso, firmado con un secreto DEDICADO
# (ni el del correo ni el de la sesion del chat), y el chat lo canjea por su propia
# sesion. Vida corta porque viaja en una URL: si queda en un historial, ya no sirve.
_SSO_SECRET = os.getenv("CHAT_SSO_SECRET", "")
_SSO_AUDIENCIA = "chat-sso"
_SSO_VIDA_SEG = 60

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
        "domain_isolation": data.get("domain_isolation", "0")
        not in ("0", "false", "False", ""),
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


@router.get("/api/chat-sso")
async def get_chat_sso_url(request: Request, username: str = Depends(get_current_user)):
    """URL de entrada al chat para el usuario de la sesion actual.

    La pide el iframe del chat. Devuelve el origen del chat con un vale de un solo
    uso; el chat lo canjea por su propia sesion. Si el chat sigue sirviendose en el
    origen del correo (embed_url relativa), no hace falta vale y se devuelve tal cual.
    """
    try:
        data = await _read(request.app.state.db_pool)
    except Exception:
        data = dict(_DEFAULTS)
    destino = (data.get("embed_url") or _DEFAULTS["embed_url"]).strip()

    # Mismo origen: el navegador ya manda la cookie del correo, no hay nada que canjear.
    if not destino.lower().startswith(("http://", "https://")):
        return {"url": destino, "origen": None, "vale": False}

    if not _SSO_SECRET:
        raise HTTPException(
            status_code=503,
            detail="El chat esta configurado en otro origen pero falta CHAT_SSO_SECRET",
        )

    from urllib.parse import urlsplit

    partes = urlsplit(destino)
    origen = f"{partes.scheme}://{partes.netloc}"
    ruta = partes.path or "/chat/"
    if partes.query:
        ruta += "?" + partes.query

    ahora = datetime.now(timezone.utc)
    vale = jwt.encode(
        {
            "sub": username,
            "aud": _SSO_AUDIENCIA,
            "jti": uuid.uuid4().hex,
            "iat": ahora,
            "exp": ahora + timedelta(seconds=_SSO_VIDA_SEG),
        },
        _SSO_SECRET,
        algorithm="HS256",
    )
    from urllib.parse import quote

    return {
        "url": f"{origen}/sso/entrar?t={vale}&r={quote(ruta, safe='/?=&')}",
        "origen": origen,
        "vale": True,
    }


@router.get("/api/admin/chat-config")
async def get_chat_config_admin(request: Request, admin: str = Depends(require_admin)):
    return _to_public(await _read(request.app.state.db_pool))


@router.put("/api/admin/chat-config")
async def put_chat_config(
    body: ChatConfigIn, request: Request, admin: str = Depends(require_admin)
):
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
            k,
            v,
        )
    return _to_public(await _read(db))
