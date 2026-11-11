"""Recuperación entre servidores: mensajes del protocolo y solicitudes en curso.

1. El servidor del remitente guarda la solicitud (testigo de un solo uso, 2 minutos) y la envía
   al servidor del destinatario.
2. El servidor del destinatario la devuelve al servidor del dominio remitente («¿la emitiste tú?»).
   Solo quien controla ese servidor puede confirmarla: así no hacen falta claves compartidas.
"""

from __future__ import annotations

import hashlib
import json
import secrets

from pydantic import BaseModel, Field

from app.config import get_settings

VERSION = 1
RUTA_BASE = "/api/federacion/v1/recuperacion"
RUTA_SOLICITAR = RUTA_BASE + "/solicitar"
RUTA_CONFIRMAR = RUTA_BASE + "/confirmar"
TTL_SOLICITUD_S = 120

ESTADO_RECUPERADO = "recalled"
ESTADO_FUERA_DE_PLAZO = "fuera_de_plazo"
ESTADO_NO_RECUPERADO = "no_recuperado"


class Solicitud(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    message_id: str = Field(min_length=3, max_length=510)
    remitente: str = Field(min_length=3, max_length=320)
    destinatario: str = Field(min_length=3, max_length=320)


def activo() -> bool:
    return bool(getattr(get_settings(), "recall_entre_servidores", True))


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


def _clave(token: str) -> str:
    return "fed:recall:" + hashlib.sha256(token.encode()).hexdigest()


def _huella(s: Solicitud) -> str:
    return json.dumps(
        [
            s.message_id.strip(),
            s.remitente.strip().lower(),
            s.destinatario.strip().lower(),
        ]
    )


async def guardar(redis, s: Solicitud) -> None:
    await redis.setex(_clave(s.token), TTL_SOLICITUD_S, _huella(s))


async def olvidar(redis, s: Solicitud) -> None:
    await redis.delete(_clave(s.token))


async def confirmar(redis, s: Solicitud) -> bool:
    """¿Esta solicitud la emitió este servidor? Vale una sola vez."""
    guardada = await redis.get(_clave(s.token))
    if isinstance(guardada, bytes):
        guardada = guardada.decode()
    if not guardada or not secrets.compare_digest(guardada, _huella(s)):
        return False
    await redis.delete(_clave(s.token))
    return True
