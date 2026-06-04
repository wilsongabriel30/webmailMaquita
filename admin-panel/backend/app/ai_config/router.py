"""Configuración de IA — permite conectar una IA propia (Ollama / gateway en tu
data center) o un proveedor por API (OpenAI y compatibles) desde el panel.
La config se guarda en la tabla ai_config (una sola fila, id=1). El webmail la
lee con fallback al .env."""
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
import httpx

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/ai-config", tags=["ai-config"])


def _db(r: Request):
    return r.app.state.db


class AiConfigIn(BaseModel):
    provider: str = "ollama"   # ollama | openai | custom
    base_url: str = ""
    api_key: str = ""          # vacío al guardar = conservar la existente
    model: str = ""
    enabled: bool = False


@router.get("")
async def get_config(request: Request, admin: dict = Depends(get_current_admin)):
    """Devuelve la config actual SIN exponer la api_key (solo si hay una)."""
    row = await _db(request).fetchrow(
        "SELECT provider, base_url, model, enabled, (api_key <> '') AS has_key, updated_at "
        "FROM ai_config WHERE id = 1"
    )
    if not row:
        return {"provider": "ollama", "base_url": "", "model": "",
                "enabled": False, "has_key": False}
    return dict(row)


@router.put("")
async def save_config(body: AiConfigIn, request: Request,
                      admin: dict = Depends(require_role("superadmin", "admin"))):
    """Guarda la config. Si api_key llega vacía, conserva la guardada."""
    await _db(request).execute(
        """
        INSERT INTO ai_config (id, provider, base_url, api_key, model, enabled, updated_at)
        VALUES (1, $1, $2, $3, $4, $5, now())
        ON CONFLICT (id) DO UPDATE SET
          provider = EXCLUDED.provider,
          base_url = EXCLUDED.base_url,
          api_key  = CASE WHEN $3 <> '' THEN $3 ELSE ai_config.api_key END,
          model    = EXCLUDED.model,
          enabled  = EXCLUDED.enabled,
          updated_at = now()
        """,
        body.provider, body.base_url, body.api_key, body.model, body.enabled,
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
        row = await _db(request).fetchrow("SELECT api_key FROM ai_config WHERE id = 1")
        key = row["api_key"] if row else ""
    base = (body.base_url or "").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            if body.provider == "ollama":
                # Ollama lista los modelos instalados
                resp = await c.get(f"{base or 'http://127.0.0.1:11434'}/api/tags")
            elif body.provider == "openai":
                resp = await c.get(
                    f"{base or 'https://api.openai.com'}/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
            else:  # custom: gateway propio (X-API-Key)
                resp = await c.get(base or "http://127.0.0.1:8000",
                                   headers={"X-API-Key": key})
        return {"ok": resp.status_code < 500, "status": resp.status_code,
                "detail": "Conexión establecida" if resp.status_code < 500
                          else f"El servidor respondió {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
