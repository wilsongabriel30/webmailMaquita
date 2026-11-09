"""Piezas comunes de la consola de Flota Maquita: registro (bitácora de solo inserción) y validaciones."""

from __future__ import annotations

import json
import uuid

from fastapi import HTTPException, Request

from app.dispositivos.comun import auditar, db, texto  # noqa: F401  (se reexportan para los routers de flota)


_JSONB = ("inventario", "parametros", "datos", "detalle")


def con_json(fila) -> dict:
    """El pool del panel devuelve JSONB como texto: se decodifica para que el navegador reciba objetos."""
    d = dict(fila)
    for k in _JSONB:
        if isinstance(d.get(k), str):
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                pass
    return d


def ip(r: Request) -> str:
    return r.headers.get("X-Real-IP", r.client.host if r.client else "")


def actor(admin: dict) -> str:
    return f"admin:{admin['username']}"


def uuid_o_400(valor, campo: str = "id") -> str:
    try:
        return str(uuid.UUID(str(valor)))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, f"{campo} con formato incorrecto")


async def anotar(conexion, r: Request, admin: dict, accion: str, *, equipo_id=None, orden_id=None, detalle=None):
    """Bitácora de Flota (flota_registro). Toda acción del panel pasa por aquí."""
    await conexion.execute(
        "INSERT INTO flota_registro (equipo_id, orden_id, actor, accion, detalle, ip) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        equipo_id, orden_id, actor(admin), accion,
        json.dumps(detalle, ensure_ascii=False, default=str) if detalle is not None else None, ip(r),
    )
