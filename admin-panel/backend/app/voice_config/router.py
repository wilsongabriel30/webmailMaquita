"""Configuración de Dictado por voz (Whisper) — permite a cada instalación del
webmail apuntar a su propio servidor de transcripción (un PC con GPU, un servidor
de IA, etc.) desde el panel, sin tocar código. Tabla voice_config (fila única).

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import httpx
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/voice-config", tags=["voice-config"])


def _db(r: Request):
    return r.app.state.db


class VoiceConfigIn(BaseModel):
    whisper_url: str = ""
    whisper_key: str = ""     # vacío al guardar = conservar la existente
    language: str = "es"
    enabled: bool = False


@router.get("")
async def get_config(request: Request, admin: dict = Depends(get_current_admin)):
    row = await _db(request).fetchrow(
        "SELECT whisper_url, language, enabled, (whisper_key <> '') AS has_key, updated_at "
        "FROM voice_config WHERE id = 1")
    if row:
        return dict(row)
    return {"whisper_url": "", "language": "es", "enabled": False, "has_key": False}


@router.put("")
async def save_config(body: VoiceConfigIn, request: Request,
                      admin: dict = Depends(require_role("superadmin", "admin"))):
    key = body.whisper_key
    if not key:
        cur = await _db(request).fetchrow("SELECT whisper_key FROM voice_config WHERE id = 1")
        key = cur["whisper_key"] if cur and cur["whisper_key"] else ""
    await _db(request).execute(
        """
        INSERT INTO voice_config (id, whisper_url, whisper_key, language, enabled, updated_at)
        VALUES (1, $1, $2, $3, $4, now())
        ON CONFLICT (id) DO UPDATE SET
          whisper_url = EXCLUDED.whisper_url, whisper_key = EXCLUDED.whisper_key,
          language = EXCLUDED.language, enabled = EXCLUDED.enabled, updated_at = now()
        """,
        body.whisper_url, key, body.language or "es", body.enabled)
    await _db(request).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) "
        "VALUES ($1,$2,$3,$4,$5)",
        admin["id"], admin["username"], "voice_config_update", body.whisper_url,
        request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    return {"ok": True}


@router.post("/test")
async def test_config(body: VoiceConfigIn, request: Request,
                      admin: dict = Depends(get_current_admin)):
    url = (body.whisper_url or "").rstrip("/")
    if not url:
        return {"ok": False, "error": "Falta la URL del servidor Whisper"}
    try:
        async with httpx.AsyncClient(timeout=6, verify=False) as c:
            r = await c.get(f"{url}/health")
        return {"ok": r.status_code == 200, "status": r.status_code,
                "detail": "Servidor de transcripción disponible" if r.status_code == 200
                          else f"Respondió {r.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}
