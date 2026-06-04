"""Dictado por voz — proxy a un servidor Whisper (transcripción de audio).

La URL y la API key del servidor Whisper se configuran desde el panel de
administración (tabla voice_config). Así cada instalación del webmail puede
apuntar a su propio servidor de transcripción (un PC con GPU, un servidor de IA,
etc.) sin tocar el código ni el nginx. Si no hay config en la tabla, usa los
valores del .env como fallback.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import os
import httpx
from fastapi import APIRouter, Request, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/mail", tags=["transcribe"])


async def _voice_config(request: Request):
    """Lee la config de dictado (voice_config) o cae al .env."""
    url = os.getenv("WHISPER_URL", "")
    key = os.getenv("WHISPER_API_KEY", "")
    lang = os.getenv("WHISPER_LANGUAGE", "es")
    enabled = bool(url)
    try:
        pool = request.app.state.db_pool
        row = await pool.fetchrow(
            "SELECT whisper_url, whisper_key, language, enabled FROM voice_config WHERE id = 1")
        if row:
            url = row["whisper_url"] or url
            key = row["whisper_key"] or key
            lang = row["language"] or lang
            enabled = row["enabled"]
    except Exception:
        pass
    return url.rstrip("/"), key, lang, enabled


@router.get("/transcribe/health")
async def transcribe_health(request: Request, username: str = Depends(get_current_user)):
    """¿Está habilitado y disponible el dictado por voz?"""
    url, key, _lang, enabled = await _voice_config(request)
    if not enabled or not url:
        return {"enabled": False, "available": False}
    try:
        async with httpx.AsyncClient(timeout=5, verify=False) as c:
            r = await c.get(f"{url}/health")
            return {"enabled": True, "available": r.status_code == 200}
    except Exception:
        return {"enabled": True, "available": False}


@router.post("/transcribe")
async def transcribe(request: Request, audio: UploadFile = File(...),
                     language: str = Form(default=""),
                     username: str = Depends(get_current_user)):
    """Recibe el audio del compositor y lo transcribe en el servidor Whisper
    configurado. Devuelve {success, text}."""
    url, key, lang, enabled = await _voice_config(request)
    if not enabled or not url:
        raise HTTPException(503, "El dictado por voz no está configurado. Actívalo en el panel de administración.")
    data = await audio.read()
    files = {"audio": (audio.filename or "recording.webm", data, audio.content_type or "application/octet-stream")}
    form = {"language": language or lang}
    headers = {"X-API-Key": key} if key else {}
    try:
        async with httpx.AsyncClient(timeout=120, verify=False) as c:
            r = await c.post(f"{url}/api/transcribe", files=files, data=form, headers=headers)
    except Exception as e:
        raise HTTPException(502, f"No se pudo contactar el servidor de transcripción: {str(e)[:120]}")
    if r.status_code != 200:
        return JSONResponse(status_code=r.status_code,
                            content={"success": False, "error": (r.text or "")[:200]})
    try:
        j = r.json()
    except Exception:
        return {"success": True, "text": (r.text or "").strip()}
    text = j.get("full_text") or j.get("text") or j.get("transcription") or j.get("texto") or ""
    return {"success": True, "text": text.strip()}
