"""Qué pasa al cambiar la contraseña de un buzón desde el panel (09/11/2026, pedido de Wilson).

«Si cambio la contraseña debe desbloquearse inmediatamente, pues por algo se hace el cambio»:
1. La cuenta queda ACTIVA (`mailbox.active = true`): Dovecot no autentica cuentas inactivas, y hasta hoy el
   panel decía «La contraseña no se aplicó correctamente» cuando en realidad sí se guardó pero la cuenta
   estaba desactivada (caso analista.pp@, 12:08).
2. Se quita el bloqueo temporal por intentos fallidos (misma clave Redis que el botón «Desbloquear»).
3. Se comprueba de verdad: `doveadm auth test` (como siempre) y, si aun así falla, el hash guardado se
   contrasta con `doveadm pw -t` para distinguir «no se guardó» de «Dovecot la rechaza por otro motivo».
"""
import asyncio
import logging
from asyncio.subprocess import PIPE

from app.wrappers.doveadm import verify_password

log = logging.getLogger("mailboxes.contrasena")


async def activar_y_desbloquear(db, username: str) -> dict:
    """Activa el buzón y borra el bloqueo por intentos fallidos. Nunca lanza: devuelve lo que hizo."""
    hecho = {"activada": False, "desbloqueada": False}
    try:
        res = await db.execute(
            "UPDATE mailbox SET active = true, modified = NOW() WHERE username = $1 AND active = false", username
        )
        hecho["activada"] = res.endswith(" 1")
    except Exception as e:  # noqa: BLE001
        log.warning("no se pudo activar %s: %s", username, e)
    try:
        from app.mailboxes.bloqueo_acceso import PREFIJO, _redis  # perezoso: bloqueo_acceso importa router

        r = _redis()
        try:
            hecho["desbloqueada"] = bool(await r.delete(f"{PREFIJO}{username}"))
        finally:
            await r.aclose()
    except Exception as e:  # noqa: BLE001
        log.warning("no se pudo quitar el bloqueo de %s: %s", username, e)
    return hecho


async def hash_coincide(db, username: str, password: str) -> bool:
    """¿El hash guardado en la BD corresponde a esta contraseña? (`doveadm pw -t`, sin privilegios)."""
    h = await db.fetchval("SELECT password FROM mailbox WHERE username = $1", username)
    if not h:
        return False
    proc = await asyncio.create_subprocess_exec("doveadm", "pw", "-t", h, "-p", password, stdout=PIPE, stderr=PIPE)
    out, err = await proc.communicate()
    return "(verified)" in (out + err).decode(errors="replace")


async def comprobar_aplicada(db, username: str, password: str) -> None:
    """Lanza RuntimeError con un mensaje claro si la contraseña nueva no sirve para entrar."""
    if await verify_password(username, password):
        return
    if await hash_coincide(db, username, password):
        raise RuntimeError(
            "La contraseña quedó guardada, pero el servidor de correo todavía no la acepta "
            "(cuenta inactiva o bloqueada por otra regla). Revise el estado del buzón e intente entrar de nuevo."
        )
    raise RuntimeError("La contraseña no se aplicó correctamente. Intente nuevamente.")
