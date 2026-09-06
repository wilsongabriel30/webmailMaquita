# -*- coding: utf-8 -*-
"""Web Push (VAPID) — notificaciones al navegador aunque la PWA esté cerrada.

Guarda las suscripciones del navegador (endpoint + claves) y envía notificaciones con
pywebpush. La clave privada VAPID vive en un archivo fuera del repo (VAPID_PRIVATE_KEY_PATH).
El disparo real (correo nuevo) lo hace el watcher de IMAP IDLE (websocket/router.py).
"""

import asyncio
import json
import logging
import os

from pywebpush import WebPushException, webpush

log = logging.getLogger("push")

VAPID_PUBLIC = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_PATH = os.getenv("VAPID_PRIVATE_KEY_PATH", "")
VAPID_SUB = os.getenv("VAPID_SUB", "mailto:admin@localhost")


def habilitado() -> bool:
    return bool(
        VAPID_PUBLIC and VAPID_PRIVATE_PATH and os.path.exists(VAPID_PRIVATE_PATH)
    )


async def asegurar_tabla(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id         SERIAL PRIMARY KEY,
            username   TEXT NOT NULL,
            endpoint   TEXT UNIQUE NOT NULL,
            p256dh     TEXT NOT NULL,
            auth       TEXT NOT NULL,
            creado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    await db.execute(
        "CREATE INDEX IF NOT EXISTS ix_push_user ON push_subscriptions(username)"
    )


async def guardar(db, username, endpoint, p256dh, auth):
    await db.execute(
        """
        INSERT INTO push_subscriptions (username, endpoint, p256dh, auth)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (endpoint) DO UPDATE SET
            username = EXCLUDED.username, p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth
    """,
        username,
        endpoint,
        p256dh,
        auth,
    )


async def borrar(db, endpoint):
    await db.execute("DELETE FROM push_subscriptions WHERE endpoint = $1", endpoint)


def _enviar_sync(sub, payload):
    webpush(
        subscription_info=sub,
        data=payload,
        vapid_private_key=VAPID_PRIVATE_PATH,
        vapid_claims={"sub": VAPID_SUB},
        timeout=10,
    )


async def enviar_a_usuario(db, username, titulo, cuerpo, url="/"):
    """Envía un push a TODAS las suscripciones del usuario. Limpia las muertas (404/410)."""
    if not habilitado():
        return 0
    try:
        filas = await db.fetch(
            "SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE username = $1",
            username,
        )
    except Exception as e:
        log.warning("push: no pude leer suscripciones de %s: %s", username, e)
        return 0
    payload = json.dumps({"title": titulo, "body": cuerpo, "url": url})
    enviados = 0
    muertas = []
    for f in filas:
        sub = {
            "endpoint": f["endpoint"],
            "keys": {"p256dh": f["p256dh"], "auth": f["auth"]},
        }
        try:
            await asyncio.to_thread(_enviar_sync, sub, payload)
            enviados += 1
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", 0)
            if code in (404, 410):
                muertas.append(f["endpoint"])
            else:
                log.warning("push a %s falló (%s): %s", username, code, e)
        except Exception as e:
            log.warning("push a %s error: %s", username, e)
    for ep in muertas:
        try:
            await db.execute("DELETE FROM push_subscriptions WHERE endpoint = $1", ep)
        except Exception:
            pass
    return enviados
