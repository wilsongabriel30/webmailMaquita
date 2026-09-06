"""Ejecución de acciones de respuesta y registro en threat_actions.

Contención dentro de los privilegios del backend: desactiva el buzón
(active=false) y mata la sesión en Redis. NO requiere sudo. El vaciado de
cola Postfix queda para el operador (maquita-contener / maquita-mailadm).
"""

import logging

logger = logging.getLogger("air.responder")


async def _log(db, action, target, detail, actor="AIR", auto=True):
    try:
        await db.execute(
            "INSERT INTO threat_actions(action,target,detail,actor,auto,created_at) "
            "VALUES($1,$2,$3,$4,$5,now())",
            action,
            target,
            detail[:500],
            actor,
            auto,
        )
    except Exception as e:
        logger.warning("no se pudo registrar threat_action: %s", e)


async def lock_account(
    db, redis, username: str, reason: str, actor="AIR", auto=True
) -> dict:
    """Contención: desactiva el buzón + limpia su sesión Redis."""
    await db.execute("UPDATE mailbox SET active=false WHERE username=$1", username)
    for k in (
        f"imap_pass:{username}",
        f"imap_master:{username}",
        f"account_blocked:{username}",
    ):
        try:
            await redis.delete(k)
        except Exception:
            pass
    await redis.set(f"account_blocked:{username}", f"AIR: {reason}"[:200], ex=86400)
    await _log(db, "account_locked", username, reason, actor, auto)
    logger.warning("AIR contuvo la cuenta %s: %s", username, reason)
    return {"locked": True, "username": username}


async def record_incident(
    db, username: str, severity: str, detail: str, auto=True
) -> None:
    await _log(db, f"incident_{severity}", username, detail, "AIR", auto)
