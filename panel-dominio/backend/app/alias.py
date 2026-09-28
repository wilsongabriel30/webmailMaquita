"""Alias de los dominios propios: direcciones que entregan en cuentas del mismo administrador.

Reglas:
- la dirección del alias y TODOS sus destinos deben ser de dominios propios, y los destinos
  deben ser cuentas que existen. Reenviar hacia afuera o hacia otro dominio lo decide el
  administrador general;
- no se toca la entrada propia de cada cuenta (address = goto): sin ella la cuenta deja de
  recibir correo;
- no se tocan las direcciones de los grupos de distribución: las gestiona su propia sección.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.alcance import exigir_alcance
from app.sesion import admin_actual, auditar
from app.validacion import destinos_de_alias, normalizar_direccion

router = APIRouter(prefix="/api/alias", tags=["alias"])



def _db(r: Request):
    return r.app.state.db


async def _es_de_grupo(db, address: str) -> bool:
    try:
        return bool(await db.fetchval("SELECT 1 FROM mail_groups WHERE lower(address) = $1", address))
    except Exception:
        return False


async def _alias(request: Request, admin: dict, address: str):
    address = str(address or "").strip().lower()
    exigir_alcance(admin, address)
    fila = await _db(request).fetchrow("SELECT address, goto, domain, active, created, modified FROM alias WHERE address = $1 AND address <> goto", address)
    if not fila or await _es_de_grupo(_db(request), address):
        raise HTTPException(404, "No encontrado")
    return fila


async def _destinos_validos(request: Request, admin: dict, valor) -> str:
    destinos = destinos_de_alias(valor)
    for d in destinos:
        if d.rsplit("@", 1)[1] not in admin["dominios"]:
            raise HTTPException(400, f"{d} no es de tus dominios. Los destinos deben ser cuentas de tus dominios.")
    existentes = await _db(request).fetch(
        "SELECT username FROM mailbox WHERE username = ANY($1::varchar[])", destinos
    )
    faltan = sorted(set(destinos) - {f["username"] for f in existentes})
    if faltan:
        raise HTTPException(400, "No existe la cuenta: " + ", ".join(faltan))
    return ",".join(destinos)


@router.get("")
async def listar(request: Request, admin: dict = Depends(admin_actual)):
    filas = await _db(request).fetch(
        """SELECT address, goto, domain, active, created, modified FROM alias a
             WHERE domain = ANY($1::varchar[]) AND address <> goto
               AND NOT EXISTS (SELECT 1 FROM mail_groups g WHERE lower(g.address) = a.address)
             ORDER BY domain, address""",
        admin["dominios"],
    )
    return [dict(f) for f in filas]


@router.post("", status_code=201)
async def crear(request: Request, admin: dict = Depends(admin_actual)):
    datos = await request.json()
    address = normalizar_direccion(datos.get("address"))
    dominio = exigir_alcance(admin, address)
    goto = await _destinos_validos(request, admin, datos.get("goto"))
    db = _db(request)
    if await db.fetchval("SELECT 1 FROM alias WHERE address = $1", address) or await _es_de_grupo(db, address):
        raise HTTPException(409, "Esa dirección ya está en uso")
    dom = await db.fetchrow("SELECT active, aliases FROM domain WHERE domain = $1", dominio)
    if not dom or not dom["active"]:
        raise HTTPException(400, "El dominio está desactivado")
    if dom["aliases"] and dom["aliases"] > 0:
        usados = await db.fetchval("SELECT count(*) FROM alias WHERE domain = $1 AND address <> goto", dominio)
        if usados >= dom["aliases"]:
            raise HTTPException(400, f"El dominio llegó a su límite de {dom['aliases']} alias")
    fila = await db.fetchrow(
        "INSERT INTO alias (address, goto, domain, active) VALUES ($1,$2,$3,true) RETURNING address, goto, domain, active, created, modified",
        address, goto, dominio,
    )
    await auditar(request, admin, "alias_crear", address, {"goto": goto})
    return dict(fila)


@router.put("/{address:path}")
async def editar(address: str, request: Request, admin: dict = Depends(admin_actual)):
    actual = await _alias(request, admin, address)
    datos = await request.json()
    goto = await _destinos_validos(request, admin, datos["goto"]) if "goto" in datos else actual["goto"]
    activa = bool(datos["active"]) if "active" in datos else actual["active"]
    fila = await _db(request).fetchrow(
        "UPDATE alias SET goto = $2, active = $3, modified = NOW() WHERE address = $1 AND address <> goto RETURNING address, goto, domain, active, created, modified",
        actual["address"], goto, activa,
    )
    await auditar(request, admin, "alias_editar", actual["address"], {"goto": goto, "active": activa})
    return dict(fila)


@router.delete("/{address:path}")
async def eliminar(address: str, request: Request, admin: dict = Depends(admin_actual)):
    actual = await _alias(request, admin, address)
    await _db(request).execute("DELETE FROM alias WHERE address = $1 AND address <> goto", actual["address"])
    await auditar(request, admin, "alias_eliminar", actual["address"], {"goto": actual["goto"]})
    return {"ok": True}
