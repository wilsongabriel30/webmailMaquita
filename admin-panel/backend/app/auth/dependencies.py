from fastapi import Request, HTTPException
from app.auth.jwt import decode_token


async def get_current_admin(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Token requerido")

    payload = decode_token(auth[7:])
    if not payload:
        raise HTTPException(401, "Token invalido o expirado")

    return {
        "id": int(payload["sub"]),
        "username": payload["username"],
        "role": payload["role"],
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
