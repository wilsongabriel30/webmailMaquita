"""Configuración de IA — permite conectar una IA propia (Ollama / gateway en tu
data center) o un proveedor por API (OpenAI y compatibles) desde el panel.
La config se guarda en la tabla ai_config (una sola fila, id=1). El webmail la
lee con fallback al .env. Si la tabla está vacía, este panel precarga lo que el
webmail usa hoy (su .env) para que veas la configuración actual."""
import os
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
import httpx

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/ai-config", tags=["ai-config"])


def _db(r: Request):
    return r.app.state.db


def _read_webmail_ai_env():
    """Lee OLLAMA_URL / IA_API_KEY del .env del webmail (carpeta hermana)."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "backend", ".env")
    vals = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("OLLAMA_URL=") or line.startswith("IA_API_KEY="):
                    k, _, v = line.partition("=")
                    vals[k] = v
    except Exception:
        pass
    return vals


class AiConfigIn(BaseModel):
    provider: str = "ollama"   # ollama | openai | custom
    base_url: str = ""
    api_key: str = ""          # vacío al guardar = conservar la existente
    model: str = ""
    enabled: bool = False


@router.get("")
async def get_config(request: Request, admin: dict = Depends(get_current_admin)):
    """Config actual SIN exponer la api_key. Si la tabla está vacía, muestra la
    del .env del webmail (lo que está en uso hoy) como referencia."""
    row = await _db(request).fetchrow(
        "SELECT provider, base_url, model, enabled, (api_key <> '') AS has_key, updated_at "
        "FROM ai_config WHERE id = 1"
    )
    if row:
        return dict(row)
    env = _read_webmail_ai_env()
    base = env.get("OLLAMA_URL", "")
    return {
        "provider": "custom" if base else "ollama",
        "base_url": base,
        "model": "",
        "enabled": False,
        "has_key": bool(env.get("IA_API_KEY")),
        "from_env": True,
    }


@router.put("")
async def save_config(body: AiConfigIn, request: Request,
                      admin: dict = Depends(require_role("superadmin", "admin"))):
    """Guarda la config. Si la api_key llega vacía, conserva la de la tabla; si
    tampoco hay en la tabla, toma la del .env del webmail (para no perderla)."""
    key = body.api_key
    if not key:
        cur = await _db(request).fetchrow("SELECT api_key FROM ai_config WHERE id = 1")
        key = (cur["api_key"] if cur and cur["api_key"] else "") or _read_webmail_ai_env().get("IA_API_KEY", "")
    await _db(request).execute(
        """
        INSERT INTO ai_config (id, provider, base_url, api_key, model, enabled, updated_at)
        VALUES (1, $1, $2, $3, $4, $5, now())
        ON CONFLICT (id) DO UPDATE SET
          provider = EXCLUDED.provider, base_url = EXCLUDED.base_url,
          api_key = EXCLUDED.api_key, model = EXCLUDED.model,
          enabled = EXCLUDED.enabled, updated_at = now()
        """,
        body.provider, body.base_url, key, body.model, body.enabled,
    )
    await _db(request).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) "
        "VALUES ($1,$2,$3,$4,$5)",
        admin["id"], admin["username"], "ai_config_update", body.provider,
        request.headers.get("X-Real-IP", request.client.host if request.client else ""),
    )
    return {"ok": True}


@router.post("/test")
async def test_config(body: AiConfigIn, request: Request,
                      admin: dict = Depends(get_current_admin)):
    """Prueba la conexión con la IA según el proveedor elegido."""
    key = body.api_key
    if not key:
        cur = await _db(request).fetchrow("SELECT api_key FROM ai_config WHERE id = 1")
        key = (cur["api_key"] if cur and cur["api_key"] else "") or _read_webmail_ai_env().get("IA_API_KEY", "")
    base = (body.base_url or "").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            if body.provider == "ollama":
                resp = await c.get(f"{base or 'http://127.0.0.1:11434'}/api/tags")
            elif body.provider == "openai":
                resp = await c.get(f"{base or 'https://api.openai.com'}/v1/models",
                                   headers={"Authorization": f"Bearer {key}"})
            else:  # custom: gateway propio (X-API-Key)
                resp = await c.get(f"{base}/api/v1/ia/status" if base else base,
                                   headers={"X-API-Key": key})
        return {"ok": resp.status_code < 500, "status": resp.status_code,
                "detail": "Conexión establecida" if resp.status_code < 500
                          else f"El servidor respondió {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
