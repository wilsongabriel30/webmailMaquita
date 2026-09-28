"""Segundo factor (código de 6 dígitos de una aplicación como Google Authenticator o Aegis).

- Es obligatorio: hasta activarlo, la cuenta solo puede cambiar su clave y configurar el código.
- Un código vale una sola vez: se guarda el último intervalo usado y no se acepta ese ni anteriores.
- Quitarlo no está al alcance del propio administrador de dominio. Si pierde el teléfono, lo
  restablece el administrador general desde su panel.
"""

import base64
import io
import time

import pyotp
import segno
from fastapi import APIRouter, Depends, HTTPException, Request

from app import config_extra
from app.sesion import admin_actual, auditar

router = APIRouter(prefix="/api/acceso/totp", tags=["acceso"])
INTERVALO = 30


def comprobar(secreto: str, codigo: str, ultimo_paso: int, ahora: float | None = None) -> int | None:
    """Devuelve el intervalo del código si es válido y no se ha usado; si no, None.

    Acepta el intervalo actual y los dos vecinos (relojes con medio minuto de desfase).
    """
    codigo = "".join(c for c in str(codigo or "") if c.isdigit())
    if len(codigo) != 6 or not secreto:
        return None
    actual = int((ahora if ahora is not None else time.time()) // INTERVALO)
    totp = pyotp.TOTP(secreto)
    for paso in (actual, actual - 1, actual + 1):
        if paso > ultimo_paso and pyotp.utils.strings_equal(totp.at(paso * INTERVALO), codigo):
            return paso
    return None


def codigo_qr(uri: str) -> str:
    """El enlace de alta como imagen SVG en un data: URI, para mostrarlo sin bibliotecas en el navegador."""
    salida = io.BytesIO()
    segno.make(uri, error="m").save(salida, kind="svg", scale=5, border=2, xmldecl=False, nl=False)
    return "data:image/svg+xml;base64," + base64.b64encode(salida.getvalue()).decode()


@router.get("/estado")
async def estado(admin: dict = Depends(admin_actual)):
    return {"activo": admin["totp"], "obligatorio": config_extra.TOTP_OBLIGATORIO}


@router.post("/iniciar")
async def iniciar(request: Request, admin: dict = Depends(admin_actual)):
    if admin["totp"]:
        raise HTTPException(400, "El segundo factor ya está activo. Si cambiaste de teléfono, pide al administrador general que lo restablezca.")
    secreto = pyotp.random_base32()
    await request.app.state.db.execute(
        "UPDATE pd_admins SET totp_secret = $2, totp_enabled = false, totp_last_step = 0 WHERE id = $1",
        admin["id"], secreto,
    )
    uri = pyotp.TOTP(secreto).provisioning_uri(name=admin["username"], issuer_name=config_extra.EMISOR)
    return {"secreto": secreto, "qr": codigo_qr(uri)}


@router.post("/activar")
async def activar(request: Request, admin: dict = Depends(admin_actual)):
    datos = await request.json()
    db = request.app.state.db
    fila = await db.fetchrow("SELECT totp_secret, totp_enabled, totp_last_step FROM pd_admins WHERE id = $1", admin["id"])
    if fila["totp_enabled"]:
        raise HTTPException(400, "El segundo factor ya está activo")
    paso = comprobar(fila["totp_secret"], datos.get("codigo"), fila["totp_last_step"])
    if paso is None:
        raise HTTPException(400, "El código no es correcto. Revisa que la hora del teléfono esté bien y prueba con el siguiente código.")
    await db.execute("UPDATE pd_admins SET totp_enabled = true, totp_last_step = $2 WHERE id = $1", admin["id"], paso)
    await auditar(request, admin, "segundo_factor_activado")
    return {"ok": True}
