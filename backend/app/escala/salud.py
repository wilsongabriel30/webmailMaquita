"""Comprobaciones de salud para balanceadores (nginx, HAProxy, Kubernetes).

- GET /api/salud → 200 si el proceso responde. No toca la base ni Redis: un fallo de
  PostgreSQL no debe hacer que el orquestador mate y reinicie procesos sanos.
- GET /api/listo → 200 si PostgreSQL y Redis contestan; 503 si no, o si el nodo está
  en drenaje (existe el archivo de drenaje). El balanceador deja de enviar tráfico a un
  nodo que responde 503 aquí.

Las respuestas no dicen versiones ni mensajes de error (son públicas). El detalle por
componente sigue en /api/health/detailed, solo para administradores.
"""

import asyncio
import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("escala.salud")

router = APIRouter(tags=["salud"])

# Si este archivo existe, /api/listo responde 503: el nodo se «drena» antes de
# reiniciarlo (lo usa deploy/escala/actualizar-sin-corte.sh).
ARCHIVO_DRENAJE = os.getenv("ESCALA_ARCHIVO_DRENAJE", "/run/maquita-webmail/drenar")
ESPERA_S = float(os.getenv("ESCALA_LISTO_ESPERA_S", "2"))

_SIN_CACHE = {"Cache-Control": "no-store"}


async def _base_ok(pool) -> bool:
    if pool is None:
        return False
    try:
        return await asyncio.wait_for(pool.fetchval("SELECT 1"), ESPERA_S) == 1
    except Exception as exc:
        logger.warning("listo: PostgreSQL no responde: %s", type(exc).__name__)
        return False


async def _redis_ok(redis) -> bool:
    if redis is None:
        return False
    try:
        return bool(await asyncio.wait_for(redis.ping(), ESPERA_S))
    except Exception as exc:
        logger.warning("listo: Redis no responde: %s", type(exc).__name__)
        return False


def en_drenaje() -> bool:
    try:
        return os.path.exists(ARCHIVO_DRENAJE)
    except Exception:
        return False


@router.get("/api/salud")
async def salud():
    return JSONResponse({"estado": "vivo"}, headers=_SIN_CACHE)


@router.get("/api/listo")
async def listo(request: Request):
    estado = request.app.state
    if getattr(estado, "cerrando", False) or en_drenaje():
        return JSONResponse({"estado": "drenando"}, status_code=503, headers=_SIN_CACHE)
    base, redis = await asyncio.gather(
        _base_ok(getattr(estado, "db_pool", None)),
        _redis_ok(getattr(estado, "redis", None)),
    )
    ok = base and redis
    return JSONResponse(
        {"estado": "listo" if ok else "no_listo"},
        status_code=200 if ok else 503,
        headers=_SIN_CACHE,
    )
