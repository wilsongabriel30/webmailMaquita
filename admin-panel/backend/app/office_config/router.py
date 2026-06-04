"""Configuración de OnlyOffice + Nextcloud — permite parametrizar desde el panel
el Document Server (vista previa de Office) y la cuenta de Nextcloud (Guardar en
Nube), sin tocar el .env. La config se guarda en la tabla office_config (una sola
fila, id=1). El webmail la lee con fallback al .env. Si la tabla está vacía, este
panel precarga lo que el webmail usa hoy (su .env) para que veas lo configurado.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import os
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
import httpx

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/office-config", tags=["office-config"])

# Claves del .env del webmail que sirven de fallback / precarga
_ENV_KEYS = [
    "ONLYOFFICE_URL", "ONLYOFFICE_SECRET",
    "NC_BASE_URL", "NC_PUBLIC_URL", "NC_ADMIN_USER", "NC_ADMIN_PASS",
]


def _db(r: Request):
    return r.app.state.db


def _read_webmail_env():
    """Lee las claves de OnlyOffice/Nextcloud del .env del webmail (hermano)."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "backend", ".env")
    vals = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                k, _, v = line.partition("=")
                if k in _ENV_KEYS:
                    vals[k] = v
    except Exception:
        pass
    return vals


class OfficeConfigIn(BaseModel):
    onlyoffice_url: str = ""
    onlyoffice_secret: str = ""   # vacío al guardar = conservar el existente
    nc_base_url: str = ""
    nc_public_url: str = ""
    nc_admin_user: str = ""
    nc_admin_pass: str = ""        # vacío al guardar = conservar el existente
    enabled: bool = False


@router.get("")
async def get_config(request: Request, admin: dict = Depends(get_current_admin)):
    """Config actual SIN exponer secretos. Si la tabla está vacía, muestra la del
    .env del webmail (lo que está en uso hoy) como referencia."""
    row = await _db(request).fetchrow(
        "SELECT onlyoffice_url, nc_base_url, nc_public_url, nc_admin_user, enabled, "
        "(onlyoffice_secret <> '') AS has_secret, (nc_admin_pass <> '') AS has_nc_pass, "
        "updated_at FROM office_config WHERE id = 1"
    )
    if row:
        return dict(row)
    env = _read_webmail_env()
    return {
        "onlyoffice_url": env.get("ONLYOFFICE_URL", ""),
        "nc_base_url": env.get("NC_BASE_URL", ""),
        "nc_public_url": env.get("NC_PUBLIC_URL", ""),
        "nc_admin_user": env.get("NC_ADMIN_USER", ""),
        "enabled": False,
        "has_secret": bool(env.get("ONLYOFFICE_SECRET")),
        "has_nc_pass": bool(env.get("NC_ADMIN_PASS")),
        "from_env": True,
    }


@router.put("")
async def save_config(body: OfficeConfigIn, request: Request,
                      admin: dict = Depends(require_role("superadmin", "admin"))):
    """Guarda la config. Los secretos vacíos conservan el valor actual (tabla o
    .env del webmail), para no perderlos al editar el resto."""
    env = _read_webmail_env()
    cur = await _db(request).fetchrow(
        "SELECT onlyoffice_secret, nc_admin_pass FROM office_config WHERE id = 1")
    secret = body.onlyoffice_secret or (cur["onlyoffice_secret"] if cur and cur["onlyoffice_secret"] else "") \
        or env.get("ONLYOFFICE_SECRET", "")
    nc_pass = body.nc_admin_pass or (cur["nc_admin_pass"] if cur and cur["nc_admin_pass"] else "") \
        or env.get("NC_ADMIN_PASS", "")
    await _db(request).execute(
        """
        INSERT INTO office_config (id, onlyoffice_url, onlyoffice_secret, nc_base_url,
                                   nc_public_url, nc_admin_user, nc_admin_pass, enabled, updated_at)
        VALUES (1, $1, $2, $3, $4, $5, $6, $7, now())
        ON CONFLICT (id) DO UPDATE SET
          onlyoffice_url = EXCLUDED.onlyoffice_url, onlyoffice_secret = EXCLUDED.onlyoffice_secret,
          nc_base_url = EXCLUDED.nc_base_url, nc_public_url = EXCLUDED.nc_public_url,
          nc_admin_user = EXCLUDED.nc_admin_user, nc_admin_pass = EXCLUDED.nc_admin_pass,
          enabled = EXCLUDED.enabled, updated_at = now()
        """,
        body.onlyoffice_url, secret, body.nc_base_url, body.nc_public_url,
        body.nc_admin_user, nc_pass, body.enabled,
    )
    await _db(request).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) "
        "VALUES ($1,$2,$3,$4,$5)",
        admin["id"], admin["username"], "office_config_update", body.onlyoffice_url,
        request.headers.get("X-Real-IP", request.client.host if request.client else ""),
    )
    return {"ok": True}


@router.post("/test")
async def test_config(body: OfficeConfigIn, request: Request,
                      admin: dict = Depends(get_current_admin)):
    """Prueba: OnlyOffice (healthcheck) y Nextcloud (status.php)."""
    env = _read_webmail_env()
    oo = (body.onlyoffice_url or env.get("ONLYOFFICE_URL", "")).rstrip("/")
    nc = (body.nc_base_url or env.get("NC_BASE_URL", "")).rstrip("/")
    out = {}
    async with httpx.AsyncClient(timeout=8, verify=False) as c:
        try:
            r = await c.get(f"{oo}/healthcheck")
            out["onlyoffice"] = {"ok": r.status_code == 200, "status": r.status_code,
                                 "detail": (r.text or "")[:60]}
        except Exception as e:
            out["onlyoffice"] = {"ok": False, "error": str(e)[:160]}
        try:
            r = await c.get(f"{nc}/status.php")
            ok = r.status_code == 200 and "installed" in (r.text or "")
            out["nextcloud"] = {"ok": ok, "status": r.status_code, "detail": (r.text or "")[:80]}
        except Exception as e:
            out["nextcloud"] = {"ok": False, "error": str(e)[:160]}
    return out
