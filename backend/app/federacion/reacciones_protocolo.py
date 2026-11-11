"""Reacciones entre servidores que usan la suite: mensajes del protocolo y avisos en curso.

Mismo esquema de confianza que la recuperación entre servidores: el servidor de quien reacciona
guarda el aviso (testigo de un solo uso, 2 minutos) y lo envía; el servidor que lo recibe se lo
devuelve al servidor del dominio de esa persona («¿lo emitiste tú?»). Sin claves compartidas.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Optional

from pydantic import BaseModel, Field

from app.config import get_settings

VERSION = 1
RUTA_BASE = "/api/federacion/v1/reacciones"
RUTA_AVISAR = RUTA_BASE + "/avisar"
RUTA_CONFIRMAR = RUTA_BASE + "/confirmar"
TTL_AVISO_S = 120


class Aviso(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    message_id: str = Field(min_length=3, max_length=510)
    usuario: str = Field(min_length=3, max_length=320)
    nombre: str = Field(default="", max_length=200)
    # None = la persona quitó su reacción.
    emoji: Optional[str] = Field(default=None, max_length=16)
    destinatarios: list[str] = Field(default_factory=list, max_length=200)


def activo() -> bool:
    return bool(getattr(get_settings(), "reacciones_entre_servidores", True))


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


def _clave(token: str) -> str:
    return "fed:reac:" + hashlib.sha256(token.encode()).hexdigest()


def _huella(a: Aviso) -> str:
    return json.dumps([a.message_id.strip(), a.usuario.strip().lower(), a.emoji or ""])


async def guardar(redis, a: Aviso) -> None:
    await redis.setex(_clave(a.token), TTL_AVISO_S, _huella(a))


async def olvidar(redis, a: Aviso) -> None:
    await redis.delete(_clave(a.token))


async def confirmar(redis, a: Aviso) -> bool:
    """¿Este aviso lo emitió este servidor? Vale una sola vez."""
    guardada = await redis.get(_clave(a.token))
    if isinstance(guardada, bytes):
        guardada = guardada.decode()
    if not guardada or not secrets.compare_digest(guardada, _huella(a)):
        return False
    await redis.delete(_clave(a.token))
    return True
