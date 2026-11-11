"""Que quien envió un correo se entere de las reacciones aunque no esté conectado (11/11/2026).

El aviso en pantalla solo lo ve quien tiene el correo abierto en ese momento. Aquí la reacción se
deja además en la campanita de notificaciones (la de Raíces: tabla `notifications` de la BD nomina,
la misma que usan las tareas), para que quede hasta que la persona la vea.
Una sola notificación por persona y correo cada 10 minutos, aunque cambie de reacción varias veces.
"""

from __future__ import annotations

import hashlib
import logging

from app.config import get_settings

logger = logging.getLogger("maquita.webmail.reacciones")

SILENCIO_S = 600


async def a_la_campanita(
    redis, autor: str, quien: str, nombre: str, emoji: str, asunto: str, message_id: str
) -> bool:
    """Deja la notificación al autor del correo. Devuelve True si se creó."""
    if not autor or autor == quien or not emoji:
        return False
    try:
        marca = hashlib.sha256(f"{message_id}|{quien}".encode()).hexdigest()[:24]
        if not await redis.set(
            f"reac:campanita:{autor}:{marca}", "1", nx=True, ex=SILENCIO_S
        ):
            return False
    except Exception:
        pass  # sin Redis se avisa igual
    try:
        import asyncpg

        from app.tareas.servicio import _nomina_dsn

        con = await asyncpg.connect(_nomina_dsn(), timeout=5)
        try:
            uid = await con.fetchval(
                """SELECT u.id FROM usuarios u LEFT JOIN trabajadores t ON t.id = u.trabajador_id
                    WHERE lower(u.email) = $1 OR lower(t.email_institucional) = $1
                    ORDER BY u.active DESC NULLS LAST, u.last_login DESC NULLS LAST LIMIT 1""",
                autor.lower(),
            )
            if not uid:
                return False
            await con.execute(
                """INSERT INTO notifications
                       (user_id, type, title, message, action_url, reference_type, is_read, created_at)
                   VALUES ($1, 'correo', $2, $3, $4, 'reaccion', false, now())""",
                uid,
                f"{nombre or quien} reaccionó {emoji} a su correo"[:255],
                f"«{asunto or '(sin asunto)'}»",
                get_settings().public_base_url.rstrip("/") + "/webmail/",
            )
            return True
        finally:
            await con.close()
    except Exception as exc:
        logger.warning("reacciones: no se pudo dejar el aviso en la campanita: %s", exc)
        return False
