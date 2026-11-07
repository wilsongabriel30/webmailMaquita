"""Remitentes bloqueados (por usuario): su correo va SIEMPRE a No deseado. Es el opuesto de los
remitentes de confianza (`confianza.py`).

La lista vive en el bloque `REMITENTES BLOQUEADOS` del script sieve activo del usuario
(`app.sieve.bloqueados_bloque`). La llena «Marcar como spam» y la vacía «No es spam»; esta API es
la de la pestaña Configuración → Remitentes bloqueados (05/11/2026). Agregar aquí una dirección la
saca de los remitentes de confianza, igual que marcar spam.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password
from app.mail.services.bloqueo_spam import DOMINIOS_PROPIOS, reescribir
from app.sieve import bloqueados_bloque
from app.sieve.router import (
    SCRIPT_NAME,
    sieve_connect,
    sieve_disconnect,
    sieve_getscript,
)

router = APIRouter(prefix="/api/mail", tags=["bloqueados"])
_CORREO = re.compile(r"^[^@\s<>\"]{1,64}@[a-z0-9.-]{1,255}$", re.I)


def _limpiar(correo: str) -> str:
    correo = (correo or "").strip().lower()
    m = re.search(r"<([^>]+)>", correo)
    return m.group(1).strip().lower() if m else correo


async def _leer(username: str, password: str) -> list[str]:
    reader, writer = await sieve_connect(username, password)
    try:
        return bloqueados_bloque.extraer(
            await sieve_getscript(reader, writer, SCRIPT_NAME)
        )
    finally:
        await sieve_disconnect(writer)


async def _password(request: Request, username: str) -> str:
    password = await get_user_password(request, username)
    if not password:
        raise HTTPException(
            400, "No se pudo abrir tu configuración de reglas; vuelve a iniciar sesión"
        )
    return password


@router.get("/remitentes-bloqueados")
async def listar(request: Request, username: str = Depends(get_current_user)):
    return {
        "remitentes": await _leer(username, await _password(request, username)),
        "maximo": bloqueados_bloque.MAXIMO,
    }


@router.post("/remitentes-bloqueados")
async def agregar(request: Request, username: str = Depends(get_current_user)):
    body = await request.json()
    correo = _limpiar(body.get("correo", ""))
    if not _CORREO.match(correo):
        raise HTTPException(400, "Correo del remitente no válido")
    if correo.rsplit("@", 1)[-1] in DOMINIOS_PROPIOS:
        raise HTTPException(
            400,
            "No se bloquean direcciones de la organización: si es un correo falso, márcalo como spam",
        )
    password = await _password(request, username)
    actuales = await _leer(username, password)
    if correo not in actuales and len(actuales) >= bloqueados_bloque.MAXIMO:
        raise HTTPException(
            400,
            f"Máximo {bloqueados_bloque.MAXIMO} remitentes bloqueados; quita alguno",
        )
    await reescribir(username, password, [correo], [])
    return {"remitentes": await _leer(username, password), "agregado": correo}


@router.delete("/remitentes-bloqueados")
async def quitar(
    request: Request,
    correo: str = Query(...),
    username: str = Depends(get_current_user),
):
    correo = _limpiar(correo)
    password = await _password(request, username)
    await reescribir(username, password, [], [correo])
    return {"remitentes": await _leer(username, password)}
