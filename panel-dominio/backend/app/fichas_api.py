"""Fichas de API del portal: crearlas (con alcance y caducidad), verlas y revocarlas.

- La ficha se muestra UNA vez al crearla; se guarda solo su hash (SHA-256) y sus primeros caracteres para
  reconocerla en la lista.
- Solo la crea una sesión abierta en pantalla (con una ficha no se llega aquí: ver fichas_alcance) y, si la cuenta
  tiene segundo factor, con un código nuevo: quien robe una sesión abierta no puede sacar una llave de un año.
- Todo queda en la auditoría (crear, revocar y cada acción hecha con ella, con su número).
"""

import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app import fichas_alcance as fa
from app import totp
from app.sesion import _hash, admin_actual, auditar

router = APIRouter(prefix="/api/fichas", tags=["fichas"])
_CONTROL = re.compile(r"[\x00-\x1f\x7f<>]")


def _fila(f) -> dict:
    return {"id": f["id"], "nombre": f["nombre"], "prefijo": f["prefijo"], "alcances": list(f["alcances"] or []),
            "creada": f["created_at"].isoformat() if f["created_at"] else None,
            "vence": f["expires_at"].isoformat() if f["expires_at"] else None,
            "ultimo_uso": f["last_used_at"].isoformat() if f["last_used_at"] else None,
            "revocada": f["revoked_at"] is not None}


@router.get("")
async def listar(request: Request, admin: dict = Depends(admin_actual)):
    filas = await request.app.state.db.fetch(
        """SELECT id, nombre, prefijo, alcances, created_at, expires_at, last_used_at, revoked_at
             FROM pd_fichas_api WHERE admin_id = $1 ORDER BY created_at DESC LIMIT 50""", admin["id"])
    return {"fichas": [_fila(f) for f in filas], "areas": fa.AREAS, "dias_maximos": fa.DIAS_MAXIMOS,
            "maximo": fa.MAXIMO_POR_CUENTA}


@router.post("", status_code=201)
async def crear(request: Request, admin: dict = Depends(admin_actual)):
    if admin.get("ficha_api"):
        raise HTTPException(403, "Una ficha de API no puede crear otras")
    datos = await request.json() if await request.body() else {}
    if not isinstance(datos, dict):
        raise HTTPException(400, "Datos no válidos")
    nombre = str(datos.get("nombre") or "").strip()
    if not 1 <= len(nombre) <= 80 or _CONTROL.search(nombre):
        raise HTTPException(400, "Ponle un nombre de 1 a 80 caracteres (sin < ni >) para reconocerla")
    alcances = fa.validar_alcances(datos.get("alcances"))
    if alcances is None:
        raise HTTPException(400, "Elige el alcance: lectura y, si hace falta, las áreas donde podrá hacer cambios")
    dias = datos.get("dias")
    if isinstance(dias, bool) or not isinstance(dias, int) or not 1 <= dias <= fa.DIAS_MAXIMOS:
        raise HTTPException(400, f"La caducidad va de 1 a {fa.DIAS_MAXIMOS} días")
    db = request.app.state.db
    cuenta = await db.fetchrow("SELECT totp_enabled, totp_secret, totp_last_step FROM pd_admins WHERE id = $1", admin["id"])
    if cuenta and cuenta["totp_enabled"]:
        paso = totp.comprobar(cuenta["totp_secret"], datos.get("codigo"), cuenta["totp_last_step"] or 0)
        if paso is None:
            await auditar(request, admin, "ficha_api_codigo_fallido")
            raise HTTPException(400, "Escribe un código nuevo de tu aplicación de segundo factor")
        await db.execute("UPDATE pd_admins SET totp_last_step = $2 WHERE id = $1", admin["id"], paso)
    activas = await db.fetchval(
        "SELECT count(*) FROM pd_fichas_api WHERE admin_id = $1 AND revoked_at IS NULL AND expires_at > NOW()", admin["id"])
    if (activas or 0) >= fa.MAXIMO_POR_CUENTA:
        raise HTTPException(409, f"Como máximo {fa.MAXIMO_POR_CUENTA} fichas activas: revoca alguna antes")
    ficha = fa.PREFIJO + secrets.token_urlsafe(32)
    vence = datetime.now(timezone.utc) + timedelta(days=dias)
    ident = await db.fetchval(
        """INSERT INTO pd_fichas_api (admin_id, nombre, prefijo, token_hash, alcances, expires_at)
           VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
        admin["id"], nombre, ficha[:12], _hash(ficha), alcances, vence)
    await auditar(request, admin, "ficha_api_crear", nombre[:255], {"id": ident, "alcances": alcances, "dias": dias})
    return {"id": ident, "ficha": ficha, "nombre": nombre, "alcances": alcances, "vence": vence.isoformat(),
            "aviso": "Cópiala ahora: no se vuelve a mostrar. Úsala en la cabecera «Authorization: Bearer …»."}


@router.delete("/{ident}")
async def revocar(ident: int, request: Request, admin: dict = Depends(admin_actual)):
    hecho = await request.app.state.db.fetchval(
        "UPDATE pd_fichas_api SET revoked_at = NOW() WHERE id = $1 AND admin_id = $2 AND revoked_at IS NULL RETURNING id",
        ident, admin["id"])
    if not hecho:
        raise HTTPException(404, "No encontrada")
    await auditar(request, admin, "ficha_api_revocar", str(ident))
    return {"ok": True}
