"""Bloqueo temporal de acceso al webmail por intentos fallidos: consultarlo y quitarlo.

El backend del correo cuenta los intentos de ingreso de cada buzón en Redis
(`login_rl:user:{buzón}`, 15 minutos desde el primer intento) y, pasados 10, responde
«Cuenta bloqueada temporalmente». Desde aquí el administrador ve qué buzones están
bloqueados ahora y cuánto les falta, y puede quitar el bloqueo en el acto.

Solo se borra el contador del buzón. No se tocan:
- `login_rl:ip:*` (contador por dirección IP, 5 minutos; no es de un buzón);
- `account_blocked:*` (bloqueo de ENVÍO por actividad sospechosa, 2 horas): es una
  contención de seguridad, no un olvido de contraseña;
- buzones inactivos o contenidos por envío masivo: se reactivan con «Activar».
"""
import os

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.mailboxes.router import _audit, _db

router = APIRouter(prefix="/api/mailboxes", tags=["mailboxes"])

PREFIJO = "login_rl:user:"
# Igual que en el backend del correo (auth/router.py, _check_login_rate_limit):
# con más de 10 intentos en la ventana el ingreso queda bloqueado.
MAX_INTENTOS = 10


def _redis():
    import redis.asyncio as aioredis

    return aioredis.from_url(
        os.environ.get("WEBMAIL_REDIS_URL") or "redis://localhost:6379/0",
        decode_responses=True,
    )


def _estado(intentos: int, ttl: int) -> dict:
    return {
        "intentos": intentos,
        "bloqueado": intentos > MAX_INTENTOS,
        "segundos_restantes": ttl if ttl > 0 else 0,
    }


@router.get("/bloqueos/activos")
async def bloqueos_activos(admin: dict = Depends(get_current_admin)):
    """Buzones con intentos fallidos de ingreso en la ventana actual (bloqueados o no)."""
    r = _redis()
    resultado = {}
    try:
        async for clave in r.scan_iter(match=f"{PREFIJO}*", count=500):
            valor = await r.get(clave)
            if valor is None:
                continue
            try:
                intentos = int(valor)
            except ValueError:
                continue
            resultado[clave[len(PREFIJO):]] = _estado(intentos, await r.ttl(clave))
    except Exception:
        raise HTTPException(503, "No se pudo consultar Redis del correo")
    finally:
        await r.aclose()
    return resultado


@router.post("/{username:path}/desbloquear")
async def desbloquear_acceso(
    username: str, request: Request,
    admin: dict = Depends(require_role("superadmin", "admin")),
):
    """Quita en el acto el bloqueo temporal de ingreso por intentos fallidos."""
    username = username.strip().lower()
    if not await _db(request).fetchval("SELECT 1 FROM mailbox WHERE username = $1", username):
        raise HTTPException(404, "Buzón no encontrado")
    r = _redis()
    clave = f"{PREFIJO}{username}"
    try:
        valor = await r.get(clave)
        ttl = await r.ttl(clave) if valor is not None else -1
        borrado = bool(await r.delete(clave))
    except Exception:
        raise HTTPException(503, "No se pudo conectar con Redis del correo")
    finally:
        await r.aclose()
    antes = _estado(int(valor) if valor and valor.isdigit() else 0, ttl)
    await _audit(request, admin, "mailbox_unlock", username, {
        "origen": "panel",
        "borrado": borrado,
        "intentos": antes["intentos"],
        "estaba_bloqueado": antes["bloqueado"],
        "segundos_restantes": antes["segundos_restantes"],
    })
    return {"ok": True, "username": username, "borrado": borrado, **antes}
