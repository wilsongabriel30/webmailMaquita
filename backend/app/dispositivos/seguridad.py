"""Credenciales de los teléfonos: códigos de enrolamiento, token por equipo y límites de ritmo.

El token del equipo es distinto de la sesión de correo: sobrevive al cambio de contraseña de la
persona y se revoca desde el panel. En la base solo se guarda su SHA-256 (es aleatorio de 48 bytes,
no necesita sal ni función lenta). Los códigos de enrolamiento son la «contraseña de instalación»:
sin uno válido, la app no activa la gestión del equipo.
"""

import hashlib
import re
import secrets

from fastapi import HTTPException, Request


def hash_secreto(valor: str) -> str:
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


def nuevo_token() -> str:
    return secrets.token_urlsafe(48)


def limpiar_codigo(codigo: str) -> str:
    return re.sub(r"[-\s]", "", (codigo or "").lower())[:64]


def ip_cliente(request: Request) -> str:
    ip = request.headers.get("X-Real-IP") or (request.client.host if request.client else "")
    return ip[:64]


async def limitar(request: Request, clave: str, maximo: int, ventana_s: int) -> None:
    """Contador en Redis; si Redis no responde no se bloquea (nginx ya limita /api/)."""
    try:
        r = request.app.state.redis
        k = f"disp:lim:{clave}"
        n = await r.incr(k)
        if n == 1:
            await r.expire(k, ventana_s)
    except Exception:
        return
    if n > maximo:
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")


async def equipo_actual(request: Request) -> dict:
    """Dependencia: identifica al teléfono por `Authorization: Bearer <token_equipo>`."""
    cab = request.headers.get("Authorization", "")
    if not cab.lower().startswith("bearer ") or len(cab) < 30:
        raise HTTPException(401, "Falta el token del equipo")
    fila = await request.app.state.db_pool.fetchrow(
        "SELECT id, estado, modo, nombre, custodio_email, custodio_nombre, ubicacion_autorizada, baliza_id, "
        "perdido_mensaje, perdido_telefono, respaldo_activo, cuota_respaldo_gb, carpeta_respaldo, push_topic FROM disp_equipos WHERE token_hash = $1",
        hash_secreto(cab[7:].strip()),
    )
    if fila is None:
        raise HTTPException(401, "Token de equipo no válido")
    if fila["estado"] in ("revocado", "baja"):
        raise HTTPException(403, "Este equipo fue dado de baja de la gestión")
    return dict(fila)
