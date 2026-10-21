"""Cuotas de sitios web de cada dominio asignado a un administrador de dominio («Mi sitio web» del portal).

Las fija aquí el superadministrador; las aplica el intermediario maquita-sitios-portal, que solo puede
leerlas (pd_cuotas_sitio). Sin fila valen las de por defecto. El uso que se muestra (sitios y disco)
sale de `maquita-sitios listar`; el de las bases lo mide el intermediario y lo ve el portal.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth.dependencies import require_superadmin

router = APIRouter(prefix="/api/admins-dominio/cuotas-sitio", tags=["admins-dominio"])
POR_DEFECTO = {"max_sitios": 1, "disco_mb": 2048, "bases_mb": 1024}


class Cuota(BaseModel):
    max_sitios: int = Field(ge=0, le=1000)
    disco_mb: int = Field(ge=0, le=10_000_000)
    bases_mb: int = Field(ge=0, le=10_000_000)


async def _hay_tabla(db) -> bool:
    return bool(await db.fetchval("SELECT to_regclass('pd_cuotas_sitio') IS NOT NULL"))


def _en(sitio: str, dominio: str) -> bool:
    return sitio == dominio or sitio.endswith("." + dominio)


async def _uso(dominios: list[str]) -> dict | None:
    from app.sitios.router import _ayudante

    try:
        sitios = (await _ayudante("listar", tiempo=120)).get("sitios", [])
    except HTTPException:
        return None  # sin sitios web en este servidor: no hay uso que mostrar
    uso = {}
    for d in dominios:
        suyos = [s for s in sitios if _en(s.get("dominio", ""), d)]
        uso[d] = {"sitios": len(suyos), "disco_mb": round(sum(float(s.get("ocupado_mb") or 0) for s in suyos), 1)}
    return uso


@router.get("")
async def listar(request: Request, admin: dict = Depends(require_superadmin)):
    db = request.app.state.db
    dominios = [f["domain"] for f in await db.fetch("SELECT DISTINCT domain FROM pd_admin_dominios ORDER BY domain")]
    disponible = await _hay_tabla(db)
    guardadas = {}
    if disponible:
        guardadas = {f["domain"]: {k: f[k] for k in POR_DEFECTO}
                     for f in await db.fetch("SELECT domain, max_sitios, disco_mb, bases_mb FROM pd_cuotas_sitio")}
    uso = await _uso(dominios)
    return {
        "disponible": disponible,
        "por_defecto": POR_DEFECTO,
        "dominios": {d: {"cuota": guardadas.get(d, POR_DEFECTO), "uso": (uso or {}).get(d)} for d in dominios},
    }


@router.put("/{dominio}")
async def guardar(dominio: str, body: Cuota, request: Request, admin: dict = Depends(require_superadmin)):
    db = request.app.state.db
    dominio = dominio.strip().lower()
    if not await db.fetchval("SELECT 1 FROM domain WHERE domain = $1", dominio):
        raise HTTPException(404, "Dominio no encontrado")
    if not await _hay_tabla(db):
        raise HTTPException(409, "Falta la tabla de cuotas: aplique panel-dominio/deploy/esquema-4-sitios.sql "
                                 "(o el ajuste 58-sitios-en-el-portal)")
    await db.execute(
        """INSERT INTO pd_cuotas_sitio (domain, max_sitios, disco_mb, bases_mb, actualizado_por, actualizado_en)
           VALUES ($1, $2, $3, $4, $5, NOW())
           ON CONFLICT (domain) DO UPDATE SET max_sitios = $2, disco_mb = $3, bases_mb = $4,
                                              actualizado_por = $5, actualizado_en = NOW()""",
        dominio, body.max_sitios, body.disco_mb, body.bases_mb, admin["username"])
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        admin["id"], admin["username"], "admin_dominio_cuota_sitio", dominio, json.dumps(body.model_dump()),
        request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    return {"ok": True, "dominio": dominio, "cuota": body.model_dump()}
