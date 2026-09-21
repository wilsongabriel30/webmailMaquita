"""Remitentes de confianza (por usuario): su correo llega SIEMPRE a la Bandeja de entrada, aunque el
filtro antispam lo marque como spam. Es el opuesto de «Bloquear remitente».

Se implementa como un script sieve personal aparte, `confianza`, que `global-before.sieve` incluye al
principio (`include :optional :personal "confianza"`), ANTES de mover a No deseado los correos con
X-Spam-Flag. Así, para un remitente de confianza, el `stop` evita que caiga en No deseado. Cada usuario
tiene el suyo; solo afecta a su propio buzón.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password
from app.sieve.router import (
    sieve_connect,
    sieve_disconnect,
    sieve_getscript,
    sieve_putscript,
)

router = APIRouter(prefix="/api/mail", tags=["confianza"])
SCRIPT = "confianza"
MAXIMO = 200
_CORREO = re.compile(r"^[^@\s<>\"]{1,64}@[a-z0-9.-]{1,255}$", re.I)


def _limpiar(correo: str) -> str:
    correo = (correo or "").strip().lower()
    m = re.search(r"<([^>]+)>", correo)
    if m:
        correo = m.group(1).strip().lower()
    return correo


def _generar(direcciones: list[str]) -> str:
    if not direcciones:
        return "# Sin remitentes de confianza.\n"
    lineas = [
        'require ["fileinto"];',
        "# Remitentes de confianza (Maquita): su correo llega a la Bandeja aunque parezca spam.",
    ]
    for d in direcciones:
        lineas.append(f'if header :contains "from" "{d}" {{ fileinto "INBOX"; stop; }}')
    return "\n".join(lineas) + "\n"


def _parsear(script: str) -> list[str]:
    return sorted(
        {
            m.group(1).lower()
            for m in re.finditer(r'header :contains "from" "([^"]+)"', script or "")
        }
    )


async def _leer(username: str, password: str) -> list[str]:
    reader, writer = await sieve_connect(username, password)
    try:
        return _parsear(await sieve_getscript(reader, writer, SCRIPT))
    finally:
        await sieve_disconnect(writer)


async def _guardar(username: str, password: str, direcciones: list[str]) -> None:
    reader, writer = await sieve_connect(username, password)
    try:
        # No se activa (setactive): lo incluye global-before.sieve; el script activo sigue siendo "webmail".
        await sieve_putscript(reader, writer, SCRIPT, _generar(direcciones))
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
