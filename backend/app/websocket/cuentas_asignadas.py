"""Avisos en tiempo real de las cuentas asignadas (multicuenta, fase 5).

El sondeo del WebSocket mira la bandeja de la persona cada 45 s. Aquí, en el mismo ciclo, se
miran también las cuentas que tiene asignadas (con la credencial maestra, como el resto de la
multicuenta). Si una sube sus no leídos se publica `new_mail_cuenta` a sus conexiones (toast,
sonido, notificación del sistema / app) y un push web «Correo nuevo en <cuenta>» cuya URL abre
el webmail ya con esa cuenta activa (`/webmail/?cuenta=<cuenta>&folder=INBOX&uid=<uid>`).
"""

import asyncio
import json
import logging
import re

from app.config import get_settings
from app.mail.services.cuentas_delegadas import credenciales_maestras, cuentas_de

logger = logging.getLogger(__name__)

# (persona, cuenta) -> último conteo de no leídos visto. -1 = aún sin referencia.
_ultimo: dict[tuple[str, str], int] = {}


async def _unseen(imap) -> tuple[int, int]:
    resp = await asyncio.wait_for(imap.status("INBOX", "(UNSEEN MESSAGES)"), timeout=10)
    unseen = total = 0
    if resp.result == "OK":
        for line in resp.lines:
            text = (
                line.decode("utf-8", "replace")
                if isinstance(line, bytes)
                else str(line)
            )
            m = re.search(r"UNSEEN\s+(\d+)", text)
            t = re.search(r"MESSAGES\s+(\d+)", text)
            if m:
                unseen = int(m.group(1))
            if t:
                total = int(t.group(1))
    return unseen, total


async def sondear(username: str, app_state, ultimo_sin_leer) -> None:
    """Un ciclo: revisa cada cuenta asignada de `username` y avisa si llegó correo."""
    from app.mail.clients.imap_client import get_imap_connection

    db = app_state.db_pool
    try:
        cuentas = await cuentas_de(db, username)
    except Exception as exc:
        logger.debug("cuentas asignadas de %s no legibles: %s", username, exc)
        return
    if not cuentas:
        return
    settings = get_settings()
    for c in cuentas:
        cuenta = str(c["email"]).lower()
        clave = (username.lower(), cuenta)
        imap = None
        try:
            login, password = credenciales_maestras(cuenta, settings)
            imap = await asyncio.wait_for(
                get_imap_connection(login, password), timeout=10
            )
            unseen, total = await _unseen(imap)
            prev = _ultimo.get(clave, -1)
            if prev != -1 and unseen > prev:
                delta = unseen - prev
                uid = await ultimo_sin_leer(imap)
                await app_state.redis.publish(
                    f"ws:user:{username}",
                    json.dumps(
                        {
                            "type": "new_mail_cuenta",
                            "cuenta": cuenta,
                            "nombre": c.get("nombre") or "",
                            "folder": "INBOX",
                            "unseen": unseen,
                            "total": total,
                            "delta": delta,
                            "uid": uid,
                        }
                    ),
                )
                try:
                    from app.push import service as _push

                    texto = (
                        f"Tienes 1 correo nuevo en {cuenta}"
                        if delta == 1
                        else f"Tienes {delta} correos nuevos en {cuenta}"
                    )
                    url = f"/webmail/?cuenta={cuenta}&folder=INBOX" + (
                        f"&uid={uid}" if uid else ""
                    )
                    await _push.enviar_a_usuario(
                        db, username, "Correo nuevo", texto, url
                    )
                except Exception:
                    pass
            _ultimo[clave] = unseen
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("sondeo de %s para %s: %s", cuenta, username, exc)
        finally:
            if imap:
                try:
                    await imap.logout()
                except Exception:
                    pass


def olvidar(username: str) -> None:
    """Al cerrarse la última conexión de la persona, se suelta su estado."""
    for k in [k for k in _ultimo if k[0] == username.lower()]:
        _ultimo.pop(k, None)
