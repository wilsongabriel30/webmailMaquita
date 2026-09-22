"""Remitentes de confianza (por usuario): su correo llega SIEMPRE a la Bandeja de entrada, aunque el
filtro antispam lo marque como spam. Es el opuesto de «Bloquear remitente».

La lista vive como un bloque delimitado DENTRO del propio script sieve activo del usuario
(ver `app.sieve.confianza_bloque`), delante de sus vacaciones y de sus reglas. El bloque hace
`fileinto "INBOX"; stop;`, y ese `stop` corta la cadena antes del filtro global posterior
(`after.sieve`), que es quien manda el correo no deseado a Junk.

Antes era un script personal aparte que el filtro global incluía con
`include :optional :personal "confianza"`. Eso tumbaba la entrega de correo: en Pigeonhole 2.4.1
ese include revienta con segfault cuando el script no existe, pese al `:optional`, y solo lo tenían
8 de los 279 buzones (21/09/2026).
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password
from app.sieve.confianza_bloque import aplicar, extraer
from app.sieve.router import (
    SCRIPT_NAME,
    sieve_connect,
    sieve_disconnect,
    sieve_getscript,
    sieve_putscript,
    sieve_setactive,
)

router = APIRouter(prefix="/api/mail", tags=["confianza"])
MAXIMO = 200
_CORREO = re.compile(r"^[^@\s<>\"]{1,64}@[a-z0-9.-]{1,255}$", re.I)


def _limpiar(correo: str) -> str:
    correo = (correo or "").strip().lower()
    m = re.search(r"<([^>]+)>", correo)
    if m:
        correo = m.group(1).strip().lower()
    return correo


async def _leer(username: str, password: str) -> list[str]:
    reader, writer = await sieve_connect(username, password)
    try:
        return extraer(await sieve_getscript(reader, writer, SCRIPT_NAME))
    finally:
        await sieve_disconnect(writer)


async def _guardar(username: str, password: str, direcciones: list[str]) -> None:
    """Reescribe el bloque dentro del script activo, sin tocar vacaciones ni reglas."""
    reader, writer = await sieve_connect(username, password)
    try:
        actual = await sieve_getscript(reader, writer, SCRIPT_NAME)
        await sieve_putscript(reader, writer, SCRIPT_NAME, aplicar(actual, direcciones))
        # Hay que activarlo: si el usuario no tenía filtros, el script no existía aún.
        await sieve_setactive(reader, writer, SCRIPT_NAME)
    finally:
        await sieve_disconnect(writer)


async def _password(request: Request, username: str) -> str:
    password = await get_user_password(request, username)
    if not password:
        raise HTTPException(
            400, "No se pudo abrir tu configuración de reglas; vuelve a iniciar sesión"
        )
    return password


@router.get("/remitentes-confiables")
async def listar(request: Request, username: str = Depends(get_current_user)):
    return {"remitentes": await _leer(username, await _password(request, username))}


@router.post("/remitentes-confiables")
async def agregar(request: Request, username: str = Depends(get_current_user)):
    body = await request.json()
    correo = _limpiar(body.get("correo", ""))
    if not _CORREO.match(correo):
        raise HTTPException(400, "Correo del remitente no válido")
    password = await _password(request, username)
    actuales = await _leer(username, password)
    if correo not in actuales:
        if len(actuales) >= MAXIMO:
            raise HTTPException(
                400, f"Máximo {MAXIMO} remitentes de confianza; quita alguno"
            )
        actuales = sorted(set(actuales) | {correo})
        await _guardar(username, password, actuales)
    return {"remitentes": actuales, "agregado": correo}


@router.delete("/remitentes-confiables")
async def quitar(
    request: Request,
    correo: str = Query(...),
    username: str = Depends(get_current_user),
):
    correo = _limpiar(correo)
    password = await _password(request, username)
    actuales = [d for d in await _leer(username, password) if d != correo]
    await _guardar(username, password, actuales)
    return {"remitentes": actuales}
