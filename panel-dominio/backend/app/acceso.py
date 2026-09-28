"""Entrar, salir, quién soy y cambiar la contraseña propia."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app import config, config_extra, totp
from app.claves import comprobar_portal, hash_portal
from app.sesion import abrir, admin_actual, auditar, cerrar
from app.validacion import exigir_clave_fuerte

router = APIRouter(prefix="/api/acceso", tags=["acceso"])
_FALLO = "Usuario o contraseña incorrectos"


@router.post("/entrar")
async def entrar(request: Request):
    datos = await request.json()
    usuario = str(datos.get("username", "")).strip().lower()[:255]
    clave = str(datos.get("password", ""))[:128]
    db = request.app.state.db
    fila = await db.fetchrow("SELECT * FROM pd_admins WHERE username = $1", usuario)

    ahora = datetime.now(timezone.utc)
    correcta = comprobar_portal(clave, fila["password_hash"] if fila else None)
    if not fila:
        raise HTTPException(401, _FALLO)
    if fila["locked_until"] and fila["locked_until"] > ahora:
        raise HTTPException(423, "Cuenta bloqueada unos minutos por intentos fallidos")
    if not correcta or not fila["active"]:
        intentos = (fila["failed_attempts"] or 0) + 1
        bloqueo = ahora + timedelta(minutes=config.MINUTOS_BLOQUEO) if intentos >= config.INTENTOS_MAXIMOS else None
        await db.execute(
            "UPDATE pd_admins SET failed_attempts = $2, locked_until = $3 WHERE id = $1",
            fila["id"], 0 if bloqueo else intentos, bloqueo,
        )
        await auditar(request, {"id": fila["id"], "username": usuario}, "entrada_fallida")
        raise HTTPException(401, _FALLO)

    paso = None
    if fila["totp_enabled"]:
        if not str(datos.get("codigo", "")).strip():
            # Clave correcta, falta el código: no es un fallo ni abre sesión.
            return {"requiere_codigo": True}
        paso = totp.comprobar(fila["totp_secret"], datos.get("codigo"), fila["totp_last_step"])
        if paso is None:
            intentos = (fila["failed_attempts"] or 0) + 1
            bloqueo = ahora + timedelta(minutes=config.MINUTOS_BLOQUEO) if intentos >= config.INTENTOS_MAXIMOS else None
            await db.execute(
                "UPDATE pd_admins SET failed_attempts = $2, locked_until = $3 WHERE id = $1",
                fila["id"], 0 if bloqueo else intentos, bloqueo)
            await auditar(request, {"id": fila["id"], "username": usuario}, "codigo_fallido")
            raise HTTPException(401, "El código no es correcto")

    await db.execute(
        """UPDATE pd_admins SET failed_attempts = 0, locked_until = NULL, last_login = NOW(),
                  totp_last_step = COALESCE($2, totp_last_step) WHERE id = $1""", fila["id"], paso)
    ficha, vence = await abrir(request, fila["id"])
    await auditar(request, {"id": fila["id"], "username": usuario}, "entrada")
    return {"token": ficha, "vence": vence.isoformat(), "debe_cambiar_clave": fila["must_change_password"],
            "debe_activar_segundo_factor": config_extra.TOTP_OBLIGATORIO and not fila["totp_enabled"]}


@router.get("/yo")
async def yo(admin: dict = Depends(admin_actual)):
    return {"username": admin["username"], "display_name": admin["display_name"], "dominios": admin["dominios"],
            "debe_cambiar_clave": admin["debe_cambiar_clave"],
            "debe_activar_segundo_factor": config_extra.TOTP_OBLIGATORIO and not admin["totp"]}


@router.post("/salir")
async def salir(request: Request, admin: dict = Depends(admin_actual)):
    await cerrar(request, admin)
    return {"ok": True}


@router.post("/clave")
async def cambiar_clave(request: Request, admin: dict = Depends(admin_actual)):
    datos = await request.json()
    db = request.app.state.db
    guardado = await db.fetchval("SELECT password_hash FROM pd_admins WHERE id = $1", admin["id"])
    if not comprobar_portal(str(datos.get("actual", ""))[:128], guardado):
        raise HTTPException(400, "La contraseña actual no es correcta")
    nueva = exigir_clave_fuerte(datos.get("nueva"), admin["username"])
    if nueva == datos.get("actual"):
        raise HTTPException(400, "La contraseña nueva debe ser distinta de la actual")
    await db.execute(
        "UPDATE pd_admins SET password_hash = $2, must_change_password = false WHERE id = $1",
        admin["id"], hash_portal(nueva),
    )
    await cerrar(request, admin, todas=True)
    await auditar(request, admin, "clave_propia")
    return {"ok": True, "sesiones_cerradas": True}
