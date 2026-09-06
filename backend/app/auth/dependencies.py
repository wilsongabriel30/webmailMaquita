from datetime import datetime, timezone

from fastapi import HTTPException, Request, status

from app.auth.jwt import decode_access_token


async def get_current_user(request: Request) -> str:
    """Usuario de la sesión actual (regla única de F-01, ver app/auth/sesiones.py).

    Un token vale si está firmado y no vencido, su `sid` existe, su `av` es la
    generación vigente del usuario y no ha pasado `abs_exp`. Deja `request.state.sid`
    y `request.state.session_kind` para el resto de la petición.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    from app.auth.sesiones import prorrogar, sesion_valida

    valida = await sesion_valida(
        request.app.state.db_pool, request.app.state.redis, payload
    )
    if valida is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired"
        )
    username, sid = valida
    # H-01: con cambio de contraseña pendiente solo se puede cambiarla o salir.
    from app.auth.bootstrap import RUTAS_PERMITIDAS, debe_cambiar_clave

    if request.url.path not in RUTAS_PERMITIDAS and await debe_cambiar_clave(
        request.app.state.db_pool, request.app.state.redis, username
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "detail": "Debes cambiar tu contraseña inicial",
                "must_change_password": True,
            },
        )
    request.state.sid = sid
    request.state.session_kind = payload.get("kind", "normal")

    # Keep-alive solo en sesiones normales: la impersonación (y las federadas) vencen
    # a su hora sin prórroga (A-17 / F-04).
    if request.state.session_kind == "normal":
        await prorrogar(
            request.app.state.redis,
            username,
            sid,
            datetime.fromtimestamp(int(payload["abs_exp"]), tz=timezone.utc),
        )
    return username


async def require_admin(request: Request) -> str:
    """Verify user is authenticated AND is an admin (superadmin or domain admin)."""
    username = await get_current_user(request)
    db = request.app.state.db_pool

    row = await db.fetchrow(
        "SELECT superadmin FROM admin WHERE username = $1 AND active = true",
        username,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return username
