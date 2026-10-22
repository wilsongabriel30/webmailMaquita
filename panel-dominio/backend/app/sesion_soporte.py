"""Sesiones de soporte: el superadministrador entra al portal «como el cliente» de UN dominio.

Las abre un vale de un solo uso que emite el panel general (ficha del dominio) o la consola
(`maquita-panel-dominio vale-soporte`). No usan la contraseña ni el segundo factor del cliente:
viven en su propia tabla (pd_sesiones_soporte), duran poco (PD_MINUTOS_SOPORTE, 60 por defecto)
y alcanzan solo el dominio del vale.

- Solo lectura (lo normal): cualquier petición que modifique (POST, PUT, PATCH, DELETE) da 403,
  salvo cerrar la sesión.
- Con acciones: se permite, y cada acción queda en pd_auditoria con la marca de soporte.
- Nunca: cambiar la contraseña ni el segundo factor del cliente (son suyos, no del soporte).
"""

import os

import asyncpg
from fastapi import HTTPException, Request


def _minutos() -> int:
    try:
        minutos = int(os.getenv("PD_MINUTOS_SOPORTE", "60"))
    except ValueError:
        minutos = 60
    return max(5, min(minutos, 240))


MINUTOS_SOPORTE = _minutos()
METODOS_LECTURA = ("GET", "HEAD", "OPTIONS")
# Lo único que se puede pedir con un método que modifica en solo lectura: cerrar la sesión.
ESCRITURA_PERMITIDA = ("/api/acceso/salir",)
# De /api/acceso/ solo esto: la contraseña y el segundo factor son del cliente.
ACCESO_PERMITIDO = ("/api/acceso/yo", "/api/acceso/salir")

SQL_SESION = """SELECT s.id, s.domain, s.superadmin, s.solo_lectura, s.expires_at
                  FROM pd_sesiones_soporte s JOIN domain d ON d.domain = s.domain
                 WHERE s.token_hash = $1 AND s.revoked_at IS NULL AND s.expires_at > NOW()"""


def modo(solo_lectura: bool) -> str:
    return "solo_lectura" if solo_lectura else "con_acciones"


def como_admin(sesion_id: int, dominio: str, superadmin: str, solo_lectura: bool, vence) -> dict:
    """La sesión de soporte con la forma de un administrador de dominio, para el resto del portal."""
    return {
        "id": None, "username": f"soporte:{superadmin}"[:255], "display_name": f"Soporte ({superadmin})",
        "sesion_id": sesion_id, "totp": True, "debe_cambiar_clave": False, "dominios": [dominio],
        "soporte": {"superadmin": superadmin, "solo_lectura": bool(solo_lectura), "modo": modo(solo_lectura),
                    "vence": vence.isoformat() if hasattr(vence, "isoformat") else str(vence)},
    }


async def buscar(db, token_hash: str) -> dict | None:
    """La sesión de soporte viva con ese hash, o None (también si este servidor aún no tiene la tabla)."""
    try:
        fila = await db.fetchrow(SQL_SESION, token_hash)
    except asyncpg.exceptions.UndefinedTableError:
        return None
    if not fila:
        return None
    return como_admin(fila["id"], fila["domain"], fila["superadmin"], fila["solo_lectura"], fila["expires_at"])


def exigir_permitido(request: Request, admin: dict) -> None:
    """403 para lo que una sesión de soporte no puede hacer (ver el docstring del módulo)."""
    ruta = request.url.path
    if ruta.startswith("/api/acceso/") and ruta not in ACCESO_PERMITIDO:
        raise HTTPException(403, "En una sesión de soporte no se tocan la contraseña ni el segundo factor del cliente")
    if admin["soporte"]["solo_lectura"] and request.method not in METODOS_LECTURA and ruta not in ESCRITURA_PERMITIDA:
        raise HTTPException(403, "Sesión de soporte de solo lectura: no se puede modificar nada")


def marcar(admin: dict, detalles: dict | None) -> dict | None:
    """Los detalles de la auditoría con la marca de soporte, si la sesión lo es."""
    soporte = admin.get("soporte")
    if not soporte:
        return detalles
    return {**(detalles or {}), "soporte": {"superadmin": soporte["superadmin"], "modo": soporte["modo"]}}
