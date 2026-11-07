"""Bienvenida al servidor nuevo tras una migración de correo (03/11/2026).

Quien llega desde otro servidor (p. ej. Zimbra) ve una ventana de bienvenida durante
BIENVENIDA_DIAS días contados desde SU primer ingreso posterior a BIENVENIDA_DESDE, no desde
la fecha del cambio: quien estaba de vacaciones la ve al volver. Solo para las cuentas de
BIENVENIDA_DOMINIOS; con la variable vacía no se muestra a nadie.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.config import get_settings

router = APIRouter(prefix="/api/bienvenida", tags=["bienvenida"])


def _dominios() -> set[str]:
    return {
        d.strip().lower()
        for d in get_settings().bienvenida_dominios.split(",")
        if d.strip()
    }


def _desde() -> datetime | None:
    texto = get_settings().bienvenida_desde.strip()
    if not texto:
        return None
    try:
        fecha = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def corresponde(username: str, ahora: datetime) -> bool:
    """¿Esta cuenta recibe la bienvenida a esta hora?"""
    desde = _desde()
    dominio = username.rsplit("@", 1)[-1].lower()
    return bool(desde) and ahora >= desde and dominio in _dominios()


@router.get("")
async def estado(request: Request, username: str = Depends(get_current_user)):
    ahora = datetime.now(timezone.utc)
    if not corresponde(username, ahora):
        return {"mostrar": False}
    db = request.app.state.db_pool
    # La primera vez que la persona entra queda anotada: desde ahí cuentan sus días.
    primera = await db.fetchval(
        """INSERT INTO bienvenida_migracion (username) VALUES ($1)
           ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username
           RETURNING primera_vez""",
        username,
    )
    dias = max(get_settings().bienvenida_dias, 1)
    hasta = primera + timedelta(days=dias)
    return {
        "mostrar": ahora < hasta,
        "dia": min((ahora - primera).days + 1, dias),
        "dias": dias,
        "hasta": hasta.isoformat(),
    }
