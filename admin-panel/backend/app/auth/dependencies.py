"""Identidad y autorización del panel.

Regla de sesión (A-9): un token solo vale si su hash sigue en admin_sessions sin revocar y
sin vencer, y si la cuenta sigue activa. El rol se lee de la BD en cada petición, no del
token: cambiar el rol o desactivar la cuenta surte efecto al instante.

Regla de roles (A-18):
  superadmin  todo.
  admin       todo salvo gestionar administradores.
  viewer      SOLO lectura (GET/HEAD/OPTIONS) y nunca correo de otras personas; puede
              administrar su propia cuenta (clave, TOTP, cierre de sesión).
  cualquier otro rol desconocido se trata como viewer (mínimo privilegio).
"""
import hashlib

from fastapi import Request, HTTPException
from app.auth.jwt import decode_token

ROLES_OPERADORES = ("superadmin", "admin")
METODOS_LECTURA = ("GET", "HEAD", "OPTIONS")
# Rutas de la propia cuenta que un viewer sí puede llamar con POST.
_CUENTA_PROPIA = ("/api/auth/logout", "/api/auth/logout-all", "/api/auth/change-password",
                  "/api/auth/verify-password", "/api/auth/totp/")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_de_la_peticion(request: Request) -> str:
    """Vale de sesión del panel: cabecera X-Admin-Token o, por compatibilidad, «Authorization: Bearer».

    El navegador usa X-Admin-Token porque «Authorization» la ocupa la clave básica de nginx cuando
    se entra al panel desde fuera de la red interna: con las dos en la misma cabecera, tras iniciar
    sesión todas las llamadas daban 401.
    """
    propio = request.headers.get("X-Admin-Token", "").strip()
    if propio:
        return propio
    auth = request.headers.get("Authorization", "")
    return auth[7:] if auth.startswith("Bearer ") else ""


async def get_current_admin(request: Request) -> dict:
    token = token_de_la_peticion(request)
    if not token:
        raise HTTPException(401, "Token requerido")
    payload = decode_token(token)
    if not payload or payload.get("purpose"):
        raise HTTPException(401, "Token inválido o expirado")

    db = request.app.state.db
    fila = await db.fetchrow(
        """SELECT s.id AS session_id, u.id, u.username, u.role, u.active
             FROM admin_sessions s JOIN admin_users u ON u.id = s.user_id
            WHERE s.token_hash = $1 AND s.revoked_at IS NULL AND s.expires_at > NOW()""",
        _hash(token),
    )
    if not fila or not fila["active"]:
        raise HTTPException(401, "Sesión cerrada o inválida")

    role = fila["role"] if fila["role"] in ROLES_OPERADORES else "viewer"
    if role == "viewer" and request.method not in METODOS_LECTURA \
            and not request.url.path.startswith(_CUENTA_PROPIA):
        raise HTTPException(403, "Tu rol es de solo lectura")

    return {
        "id": fila["id"],
        "username": fila["username"],
        "role": role,
        "session_id": fila["session_id"],
        "totp": bool(payload.get("totp")),
    }


async def require_superadmin(request: Request) -> dict:
    admin = await get_current_admin(request)
    if admin["role"] != "superadmin":
        raise HTTPException(403, "Se requiere rol superadmin")
    return admin


def require_role(*roles):
    async def dep(request: Request) -> dict:
        admin = await get_current_admin(request)
        if admin["role"] not in roles:
            separator = ", "
            raise HTTPException(403, f"Se requiere rol: {separator.join(roles)}")
        return admin
    return dep


# Lectura de correo ajeno (visor, cuarentena, recuperación): solo operadores.
require_operador = require_role(*ROLES_OPERADORES)
