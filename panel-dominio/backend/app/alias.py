"""Alias de los dominios propios: direcciones que entregan en una o varias cuentas.

No aparecen aquí, porque tienen su propia sección y tocarlas desde esta rompería la entrega:
- las cuentas (su fila entrega en el propio buzón y, si tienen reenvío, también en otros);
- los grupos de distribución.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app import destinos
from app.alcance import exigir_alcance
from app.sesion import admin_actual, auditar
from app.validacion import normalizar_direccion

router = APIRouter(prefix="/api/alias", tags=["alias"])


def _db(r: Request):
    return r.app.state.db


async def ocupada(db, address: str) -> bool:
    """¿La dirección ya es una cuenta, un alias o un grupo?"""
    return bool(await db.fetchval(
        """SELECT 1 WHERE EXISTS (SELECT 1 FROM alias WHERE address = $1)
                      OR EXISTS (SELECT 1 FROM mailbox WHERE username = $1)
                      OR EXISTS (SELECT 1 FROM mail_groups WHERE lower(address) = $1)""",
        address))


async def _alias(request: Request, admin: dict, address: str):
    address = str(address or "").strip().lower()
    exigir_alcance(admin, address)
    fila = await _db(request).fetchrow(
        """SELECT address, goto, domain, active, created, modified FROM alias a
            WHERE address = $1
              AND NOT EXISTS (SELECT 1 FROM mailbox m WHERE m.username = a.address)
              AND NOT EXISTS (SELECT 1 FROM mail_groups g WHERE lower(g.address) = a.address)""",
        address)
    if not fila:
        raise HTTPException(404, "No encontrado")
    return fila


@router.get("")
async def listar(request: Request, admin: dict = Depends(admin_actual)):
    filas = await _db(request).fetch(
        """SELECT address, goto, domain, active, created, modified FROM alias a
            WHERE domain = ANY($1::varchar[])
              AND NOT EXISTS (SELECT 1 FROM mailbox m WHERE m.username = a.address)
              AND NOT EXISTS (SELECT 1 FROM mail_groups g WHERE lower(g.address) = a.address)
            ORDER BY domain, address""",
        admin["dominios"])
    return [dict(f) for f in filas]


@router.post("", status_code=201)
async def crear(request: Request, admin: dict = Depends(admin_actual)):
    datos = await request.json()
    address = normalizar_direccion(datos.get("address"))
    dominio = exigir_alcance(admin, address)
    db = _db(request)
    lista, externos = await destinos.validar(db, admin, datos.get("goto"), salvo=address)
    if not lista:
        raise HTTPException(400, "Indica al menos un destino distinto del propio alias")
    if await ocupada(db, address):
        raise HTTPException(409, "Esa dirección ya está en uso")
    dom = await db.fetchrow("SELECT active, aliases FROM domain WHERE domain = $1", dominio)
    if not dom or not dom["active"]:
        raise HTTPException(400, "El dominio está desactivado")
    if dom["aliases"] and dom["aliases"] > 0:
        usados = await db.fetchval(
            """SELECT count(*) FROM alias a WHERE domain = $1
                AND NOT EXISTS (SELECT 1 FROM mailbox m WHERE m.username = a.address)""", dominio)
        if usados >= dom["aliases"]:
            raise HTTPException(400, f"El dominio llegó a su límite de {dom['aliases']} alias")
    fila = await db.fetchrow(
        """INSERT INTO alias (address, goto, domain, active) VALUES ($1,$2,$3,true)
           RETURNING address, goto, domain, active, created, modified""",
        address, ",".join(lista), dominio)
    await auditar(request, admin, "alias_crear", address, {"goto": lista, "externos": externos})
    return dict(fila)


@router.put("/{address:path}")
async def editar(address: str, request: Request, admin: dict = Depends(admin_actual)):
    actual = await _alias(request, admin, address)
    datos = await request.json()
    goto, externos = actual["goto"], []
    if "goto" in datos:
        lista, externos = await destinos.validar(_db(request), admin, datos["goto"], salvo=actual["address"])
        if not lista:
            raise HTTPException(400, "Indica al menos un destino distinto del propio alias")
        goto = ",".join(lista)
    activa = bool(datos["active"]) if "active" in datos else actual["active"]
    fila = await _db(request).fetchrow(
        """UPDATE alias SET goto = $2, active = $3, modified = NOW() WHERE address = $1
           RETURNING address, goto, domain, active, created, modified""",
        actual["address"], goto, activa)
    await auditar(request, admin, "alias_editar", actual["address"], {"goto": goto.split(","), "externos": externos, "active": activa})
    return dict(fila)


@router.delete("/{address:path}")
async def eliminar(address: str, request: Request, admin: dict = Depends(admin_actual)):
    actual = await _alias(request, admin, address)
    await _db(request).execute("DELETE FROM alias WHERE address = $1", actual["address"])
    await auditar(request, admin, "alias_eliminar", actual["address"], {"goto": actual["goto"]})
    return {"ok": True}
