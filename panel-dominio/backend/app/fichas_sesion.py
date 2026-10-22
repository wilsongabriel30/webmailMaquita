"""Autenticación con una ficha de API del portal («Authorization: Bearer mqd_…»).

La ficha se busca por su hash, igual que una sesión, con las mismas condiciones de la cuenta (activa, sin la
contraseña inicial y con segundo factor si es obligatorio) más las suyas: no revocada, no vencida y con alcance para
el método y la ruta de la petición. El segundo factor de la interfaz no se debilita: una ficha solo la puede crear
una sesión abierta con él, y con una ficha no se puede tocar la cuenta ni crear otras fichas.
"""

import hashlib

from fastapi import HTTPException, Request

from app import config_extra, fichas_alcance


async def admin_de_ficha(request: Request, ficha: str) -> dict:
    db = request.app.state.db
    fila = await db.fetchrow(
        """SELECT f.id AS ficha_id, f.alcances, a.id, a.username, a.display_name, a.active, a.must_change_password,
                  a.totp_enabled
             FROM pd_fichas_api f JOIN pd_admins a ON a.id = f.admin_id
            WHERE f.token_hash = $1 AND f.revoked_at IS NULL AND f.expires_at > NOW()""",
        hashlib.sha256(ficha.encode()).hexdigest(),
    )
    if not fila or not fila["active"]:
        raise HTTPException(401, "Ficha de API revocada, vencida o de una cuenta desactivada")
    if fila["must_change_password"]:
        raise HTTPException(403, "Cambia tu contraseña inicial antes de usar la API")
    if config_extra.TOTP_OBLIGATORIO and not fila["totp_enabled"]:
        raise HTTPException(403, "Activa el segundo factor antes de usar la API")
    alcances = list(fila["alcances"] or [])
    if not fichas_alcance.permitido(alcances, request.method, request.url.path):
        raise HTTPException(403, "La ficha de API no tiene permiso para esto")
    await db.execute(
        """UPDATE pd_fichas_api SET last_used_at = NOW(), last_ip = $2
            WHERE id = $1 AND (last_used_at IS NULL OR last_used_at < NOW() - INTERVAL '1 minute')""",
        fila["ficha_id"], request.headers.get("X-Real-IP", request.client.host if request.client else "")[:45])
    dominios = await db.fetch(
        """SELECT d.domain FROM pd_admin_dominios p JOIN domain d ON d.domain = p.domain
            WHERE p.admin_id = $1 ORDER BY d.domain""",
        fila["id"],
    )
    return {
        "id": fila["id"], "username": fila["username"], "display_name": fila["display_name"], "sesion_id": None,
        "totp": fila["totp_enabled"], "debe_cambiar_clave": False, "dominios": [d["domain"] for d in dominios],
        "ficha_api": fila["ficha_id"], "alcances": alcances,
    }
