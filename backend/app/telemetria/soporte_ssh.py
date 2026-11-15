"""Comando propio «reparar_ssh» para los equipos con Teams Maquita (13/11/2026).

Tecnología PROPIA, SIN Kaspersky: el soporte encola una reparación de SSH para un
equipo; el Teams (en su latido de telemetría) la recoge y deja la bandera
`%ProgramData%\\MaquitaTeams\\reparar-ssh.pedido`; la Tarea Programada SYSTEM
«Maquita Soporte SSH» la ejecuta en <5 min y la app reporta el resultado. Así el
acceso SSH de soporte no depende de ADMAQUITA/KSC (que se darán de baja).

    GET  /api/telemetria/app/soporte/pendiente?equipo=NOMBRE   (sesión) -> {reparar_ssh, id}
    POST /api/telemetria/app/soporte/resultado  {id, estado, detalle}   (sesión)
    POST /api/telemetria/app/soporte/reparar-ssh {equipo}              (admin) -> encola
    GET  /api/telemetria/app/soporte/estado?equipo=NOMBRE             (admin) -> últimos
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.auth.dependencies import require_admin
from app.auth.jwt import decode_access_token

router_soporte = APIRouter()

DDL = """
CREATE TABLE IF NOT EXISTS app_soporte_ssh (
    id           BIGSERIAL PRIMARY KEY,
    equipo       TEXT NOT NULL,
    tipo         TEXT NOT NULL DEFAULT 'reparar_ssh',
    estado       TEXT NOT NULL DEFAULT 'pendiente',   -- pendiente|entregado|hecho|fallido
    pedido_por   TEXT NOT NULL DEFAULT '',
    pedido_en    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    entregado_en TIMESTAMPTZ,
    resuelto_en  TIMESTAMPTZ,
    resultado    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_soporte_ssh_equipo ON app_soporte_ssh (lower(equipo), estado);
"""


async def asegurar_tabla_soporte(pool):
    await pool.execute(DDL)


def _hay_sesion(request: Request) -> bool:
    tok = request.cookies.get("access_token")
    if not tok:
        return False
    try:
        return bool(decode_access_token(tok))
    except Exception:
        return False


def _norm(s: str) -> str:
    return (s or "").strip()


class Resultado(BaseModel):
    id: int
    estado: str = Field(..., max_length=20)  # hecho | fallido
    detalle: str = ""


class Reparar(BaseModel):
    equipo: str = Field(..., max_length=120)


@router_soporte.get("/app/soporte/pendiente")
async def pendiente(request: Request, equipo: str):
    """La app Teams (con su sesión) pregunta si su equipo tiene una reparación de SSH
    pendiente. Marca 'entregado' lo que entrega. Es benigno: solo dispara el
    auto-reparador local (acción fija, no ejecuta nada arbitrario)."""
    if not _hay_sesion(request):
        return {"reparar_ssh": False}
    eq = _norm(equipo)
    if not eq:
        return {"reparar_ssh": False}
    async with request.app.state.db_pool.acquire() as db:
        fila = await db.fetchrow(
            "UPDATE app_soporte_ssh SET estado='entregado', entregado_en=NOW() "
            "WHERE id = (SELECT id FROM app_soporte_ssh WHERE lower(equipo)=lower($1) "
            "            AND estado='pendiente' ORDER BY pedido_en LIMIT 1) "
            "RETURNING id",
            eq,
        )
    if not fila:
        return {"reparar_ssh": False}
    return {"reparar_ssh": True, "id": fila["id"]}


@router_soporte.post("/app/soporte/resultado", status_code=202)
async def resultado(request: Request, body: Resultado):
    if not _hay_sesion(request):
        return {"ok": False}
    estado = "hecho" if body.estado == "hecho" else "fallido"
    async with request.app.state.db_pool.acquire() as db:
        await db.execute(
            "UPDATE app_soporte_ssh SET estado=$2, resuelto_en=NOW(), resultado=$3 "
            "WHERE id=$1 AND estado IN ('entregado','pendiente')",
            body.id,
            estado,
            (body.detalle or "")[:500],
        )
    return {"ok": True}


@router_soporte.post("/app/soporte/reparar-ssh", status_code=201)
async def encolar(request: Request, body: Reparar, admin: str = Depends(require_admin)):
    eq = _norm(body.equipo)
    if not eq:
        return {"ok": False, "error": "equipo vacío"}
    async with request.app.state.db_pool.acquire() as db:
        ya = await db.fetchval(
            "SELECT id FROM app_soporte_ssh WHERE lower(equipo)=lower($1) "
            "AND estado IN ('pendiente','entregado') ORDER BY pedido_en DESC LIMIT 1",
            eq,
        )
        if ya:
            return {"ok": True, "id": ya, "nota": "ya había una pendiente"}
        cid = await db.fetchval(
            "INSERT INTO app_soporte_ssh (equipo, pedido_por) VALUES ($1,$2) RETURNING id",
            eq,
            admin,
        )
    return {"ok": True, "id": cid}


@router_soporte.get("/app/soporte/estado")
async def estado(request: Request, equipo: str, admin: str = Depends(require_admin)):
    eq = _norm(equipo)
    async with request.app.state.db_pool.acquire() as db:
        filas = await db.fetch(
            "SELECT id, estado, pedido_por, pedido_en, entregado_en, resuelto_en, resultado "
            "FROM app_soporte_ssh WHERE lower(equipo)=lower($1) ORDER BY pedido_en DESC LIMIT 10",
            eq,
        )
    return {"equipo": eq, "comandos": [dict(f) for f in filas]}
