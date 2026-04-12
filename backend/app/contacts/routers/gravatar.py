"""Gravatar — verificación y URL de avatar desde Gravatar."""
import hashlib
import json
import logging

import httpx
from fastapi import APIRouter, Request, Depends, Query

from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

GRAVATAR_CACHE_TTL = 86400  # 24 horas


@router.get("/gravatar")
async def check_gravatar(
    request: Request,
    email: str = Query(..., description="Email para buscar Gravatar"),
    username: str = Depends(get_current_user),
):
    """Verifica si un email tiene Gravatar y retorna la URL."""
    email_clean = email.strip().lower()
    if not email_clean:
        return {"has_avatar": False}

    md5_hash = hashlib.md5(email_clean.encode("utf-8")).hexdigest()
    cache_key = f"gravatar:{md5_hash}"

    # Revisar cache Redis
    redis = request.app.state.redis
    cached = await redis.get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except (json.JSONDecodeError, TypeError):
            pass

    # Consultar Gravatar
    check_url = f"https://www.gravatar.com/avatar/{md5_hash}?d=404&s=200"
    result = {"has_avatar": False}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.head(check_url)
            if resp.status_code == 200:
                result = {
                    "has_avatar": True,
                    "url": f"https://www.gravatar.com/avatar/{md5_hash}?s=200",
                }
    except Exception as e:
        logger.warning(f"Error consultando Gravatar para {email_clean}: {e}")

    # Cachear resultado
    try:
        await redis.set(cache_key, json.dumps(result), ex=GRAVATAR_CACHE_TTL)
    except Exception:
        pass

    return result
