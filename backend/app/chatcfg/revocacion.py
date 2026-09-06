"""Empuje de revocaciones del correo al chat (F-03).

El chat vive en otro origen y tiene su propio Redis: no ve el estado de sesión del correo.
Cada revocación (logout, «cerrar todas», cambio de contraseña, reset, desactivación,
contención AIR) se le empuja a `POST /api/chat/sesion/revocar` con el secreto compartido
de servicios. Tres intentos con pausa; si al final no llega, ERROR con la marca
REVOCACION_CHAT_FALLIDA: nunca en silencio (DECISIONES.md D-4).

La URL del chat sale de CHAT_INTERNAL_URL o, si no, del origen de `embed_url` en la
configuración del chat (solo si es absoluta: si es relativa, el chat comparte origen y
lee la misma cookie del correo, así que no hay nada que empujar).
"""

import asyncio
import logging
import os
from urllib.parse import urlsplit

import httpx

from app.auth import sesiones
from app.tareas.avisos import _secreto as _secreto_servicios

log = logging.getLogger("seguridad.sesiones")
security_log = logging.getLogger("security")
_ESPERAS = (0, 2, 6)
_app = None


async def _url_chat() -> str | None:
    fija = (os.getenv("CHAT_INTERNAL_URL") or "").strip().rstrip("/")
    if fija:
        return fija
    if _app is None:
        return None
    try:
        from app.chatcfg.router import _read

        data = await _read(_app.state.db_pool)
    except Exception:
        return None
    destino = (data.get("embed_url") or "").strip()
    if not destino.lower().startswith(("http://", "https://")):
        return None
    p = urlsplit(destino)
    return f"{p.scheme}://{p.netloc}"


async def _empujar(username: str, sid: str, av: int, motivo: str) -> None:
    url = await _url_chat()
    if not url:
        log.debug("revocación %s sin chat en otro origen: nada que empujar", username)
        return
    secreto = _secreto_servicios()
    if not secreto:
        security_log.error(
            "REVOCACION_CHAT_FALLIDA user=%s sid=%s error=sin NOTIF_SECRET",
            username,
            sid,
        )
        return
    ultimo = ""
    for espera in _ESPERAS:
        if espera:
            await asyncio.sleep(espera)
        try:
            async with httpx.AsyncClient(timeout=6) as c:
                r = await c.post(
                    f"{url}/api/chat/sesion/revocar",
                    json={
                        "user": username,
                        "sid": sid,
                        "av": av,
                        "motivo": motivo[:60],
                    },
                    headers={"X-Notif-Secret": secreto},
                )
            if r.status_code == 200:
                log.info(
                    "revocación empujada al chat user=%s sid=%s desconectados=%s",
                    username,
                    sid,
                    (r.json() or {}).get("desconectados"),
                )
                return
            ultimo = f"HTTP {r.status_code}"
        except Exception as exc:
            ultimo = type(exc).__name__
    security_log.error(
        "REVOCACION_CHAT_FALLIDA user=%s sid=%s av=%s motivo=%s error=%s",
        username,
        sid,
        av,
        motivo,
        ultimo,
    )


async def _oyente(username: str, sid: str, av: int, motivo: str) -> None:
    """No bloquea la revocación: el empuje corre aparte, con sus reintentos."""
    asyncio.create_task(_empujar(username, sid, av, motivo))


def registrar(app) -> None:
    global _app
    _app = app
    if _oyente not in sesiones.OYENTES_REVOCACION:
        sesiones.OYENTES_REVOCACION.append(_oyente)
