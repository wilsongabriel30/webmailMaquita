"""Aviso push a los teléfonos vía ntfy autoalojado (UnifiedPush, sin Google).

El backend solo publica un «sync» (sin contenido) en el tema secreto del equipo; el teléfono despierta
y hace su latido para traer los mensajes o comandos. Publicar es best-effort: si ntfy no responde, el
latido periódico sigue entregándolo igual, así que un fallo aquí nunca rompe la acción del panel.
"""

import asyncio
import logging
import os

import httpx

logger = logging.getLogger("dispositivos")
_URL = os.environ.get("NTFY_URL_INTERNO", "http://127.0.0.1:2586")
_TOKEN = os.environ.get("NTFY_TOKEN", "")
_cliente: httpx.AsyncClient | None = None


def _c() -> httpx.AsyncClient:
    global _cliente
    if _cliente is None:
        _cliente = httpx.AsyncClient(timeout=4.0)
    return _cliente


async def _publicar(topic: str, motivo: str) -> None:
    if not topic or not _TOKEN:
        return
    try:
        await _c().post(f"{_URL}/{topic.strip()}", content=b"sync",
                        headers={"Authorization": f"Bearer {_TOKEN}", "Priority": "high",
                                 "Title": "Maquita", "X-Tags": motivo, "Cache": "yes"})
    except Exception:
        logger.debug("push_fallo topic=%s", topic, exc_info=True)


def avisar(topic: str | None, motivo: str = "sync") -> None:
    """Dispara el aviso en segundo plano; nunca bloquea ni propaga errores."""
    if topic:
        asyncio.create_task(_publicar(topic, motivo))


async def avisar_equipos(db, equipo_ids: list[int], motivo: str = "sync") -> None:
    if not equipo_ids:
        return
    filas = await db.fetch("SELECT push_topic FROM disp_equipos WHERE id = ANY($1::int[]) AND push_topic IS NOT NULL", equipo_ids)
    for f in filas:
        avisar(f["push_topic"], motivo)
