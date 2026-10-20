"""Código de un solo uso de T-74: 43 caracteres base64url (256 bits), 10 minutos, atado al
`machine_guid`. En la base solo queda su SHA-256: quien lea la tabla no puede canjear nada.
"""

from __future__ import annotations

import hashlib
import re
import secrets

VIGENCIA_S = 600
FORMATO = re.compile(r"^[A-Za-z0-9_-]{43}$")


def huella(codigo: str) -> str:
    return hashlib.sha256(codigo.encode()).hexdigest()


async def emitir(db, *, user_email, machine_guid, equipo, app, decision, ip) -> str:
    codigo = secrets.token_urlsafe(32)
    # Un código vivo por equipo: el anterior sin canjear deja de valer.
    await db.execute(
        "UPDATE respaldos_codigos SET anulado_en = NOW(), motivo = 'reemplazado' "
        "WHERE machine_guid = $1 AND usado_en IS NULL AND anulado_en IS NULL",
        machine_guid,
    )
    await db.execute(
        "INSERT INTO respaldos_codigos (codigo_hash, user_email, machine_guid, equipo, app, clientid, "
        "cliente, nuevo, caduca_en, ip_alta) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW() + make_interval(secs => $9), $10)",
        huella(codigo),
        user_email,
        machine_guid,
        equipo,
        app,
        decision["clientid"],
        decision["cliente"],
        decision["nuevo"],
        VIGENCIA_S,
        ip,
    )
    return codigo


async def buscar(db, codigo: str):
    return await db.fetchrow(
        "SELECT id, user_email, machine_guid::text AS machine_guid, equipo, app, clientid, cliente, nuevo, "
        "usado_en, anulado_en, caduca_en <= NOW() AS caducado FROM respaldos_codigos WHERE codigo_hash = $1",
        huella(codigo),
    )


async def anular(db, codigo_id: int, motivo: str) -> None:
    await db.execute(
        "UPDATE respaldos_codigos SET anulado_en = NOW(), motivo = $2 WHERE id = $1 AND anulado_en IS NULL",
        codigo_id,
        motivo,
    )


async def marcar_usado(db, codigo_id: int, ip: str) -> bool:
    """Atómico: si dos canjes llegan a la vez, solo uno gana."""
    return bool(
        await db.fetchval(
            "UPDATE respaldos_codigos SET usado_en = NOW(), ip_canje = $2 WHERE id = $1 AND usado_en IS NULL "
            "AND anulado_en IS NULL AND caduca_en > NOW() RETURNING id",
            codigo_id,
            ip,
        )
    )
