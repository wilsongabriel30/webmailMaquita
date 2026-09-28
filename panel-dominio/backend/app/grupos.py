"""Grupos de distribución: una dirección que reparte el correo entre sus miembros.

El grupo vive en `mail_groups` y sus miembros en `mail_group_members`; la entrega real la hace
la fila del grupo en `alias`, que se rehace cada vez que cambia algo. Un grupo pausado o sin
miembros que reciban no tiene fila en `alias`: el correo que le escriban se rechaza en vez de
perderse en silencio.

Miembros de fuera de los dominios propios: solo si el grupo los permite expresamente.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.alcance import exigir_alcance
from app.alias import ocupada
from app.destinos import es_propio
from app.sesion import admin_actual, auditar
from app.validacion import normalizar_direccion, texto_limpio

router = APIRouter(prefix="/api/grupos", tags=["grupos"])
MAX_MIEMBROS = 500


def _db(r: Request):
    return r.app.state.db


async def _grupo(request: Request, admin: dict, grupo_id: int):
    fila = await _db(request).fetchrow(
        "SELECT id, address, name, description, domain, active, allow_external FROM mail_groups WHERE id = $1", grupo_id)
    if not fila or fila["domain"] not in admin["dominios"]:
        raise HTTPException(404, "No encontrado")
    return fila


async def sincronizar(con, grupo) -> None:
    """Rehace la fila del grupo en `alias` a partir de sus miembros."""
    miembros = await con.fetch(
        "SELECT member_email FROM mail_group_members WHERE group_id = $1 AND receive ORDER BY member_email", grupo["id"])
    if not miembros or not grupo["active"]:
        await con.execute("DELETE FROM alias WHERE address = $1", grupo["address"])
        return
    await con.execute(
        """INSERT INTO alias (address, goto, domain, active) VALUES ($1, $2, $3, true)
           ON CONFLICT (address) DO UPDATE SET goto = EXCLUDED.goto, active = true, modified = NOW()""",
        grupo["address"], ",".join(m["member_email"] for m in miembros), grupo["domain"])


@router.get("")
async def listar(request: Request, admin: dict = Depends(admin_actual)):
    db = _db(request)
    grupos = await db.fetch(
        """SELECT id, address, name, description, domain, active, allow_external FROM mail_groups
            WHERE domain = ANY($1::varchar[]) ORDER BY domain, address""", admin["dominios"])
    miembros = await db.fetch(
        """SELECT m.id, m.group_id, m.member_email, m.member_name, m.receive FROM mail_group_members m
             JOIN mail_groups g ON g.id = m.group_id
            WHERE g.domain = ANY($1::varchar[]) ORDER BY m.member_email""", admin["dominios"])
    por_grupo: dict[int, list] = {}
    for m in miembros:
        por_grupo.setdefault(m["group_id"], []).append({
            "id": m["id"], "email": m["member_email"], "nombre": m["member_name"] or "",
            "recibe": m["receive"], "externo": not es_propio(admin, m["member_email"]),
        })
    return [{**dict(g), "miembros": por_grupo.get(g["id"], [])} for g in grupos]


@router.post("", status_code=201)
async def crear(request: Request, admin: dict = Depends(admin_actual)):
    datos = await request.json()
    address = normalizar_direccion(datos.get("address"))
    dominio = exigir_alcance(admin, address)
    db = _db(request)
    if await ocupada(db, address):
        raise HTTPException(409, "Esa dirección ya está en uso")
    dom = await db.fetchval("SELECT active FROM domain WHERE domain = $1", dominio)
    if not dom:
        raise HTTPException(400, "El dominio está desactivado")
    fila = await db.fetchrow(
        """INSERT INTO mail_groups (address, name, description, domain, allow_external)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING id, address, name, description, domain, active, allow_external""",
        address, texto_limpio(datos.get("name")), texto_limpio(datos.get("description"), 1000),
        dominio, bool(datos.get("allow_external")))
    await auditar(request, admin, "grupo_crear", address)
    return {**dict(fila), "miembros": []}


@router.put("/{grupo_id}")
async def editar(grupo_id: int, request: Request, admin: dict = Depends(admin_actual)):
    grupo = await _grupo(request, admin, grupo_id)
    datos = await request.json()
    externos = bool(datos["allow_external"]) if "allow_external" in datos else grupo["allow_external"]
    db = _db(request)
    if grupo["allow_external"] and not externos:
        miembros = await db.fetch("SELECT member_email FROM mail_group_members WHERE group_id = $1", grupo_id)
        fuera = [m["member_email"] for m in miembros if not es_propio(admin, m["member_email"])]
        if fuera:
            raise HTTPException(400, "Quita antes a los miembros de fuera: " + ", ".join(fuera[:5]))
    async with db.acquire() as con, con.transaction():
        nuevo = await con.fetchrow(
            """UPDATE mail_groups SET name = $2, description = $3, active = $4, allow_external = $5, modified_at = NOW()
                WHERE id = $1 RETURNING id, address, name, description, domain, active, allow_external""",
            grupo_id,
            texto_limpio(datos["name"]) if "name" in datos else grupo["name"],
            texto_limpio(datos["description"], 1000) if "description" in datos else grupo["description"],
            bool(datos["active"]) if "active" in datos else grupo["active"],
            externos)
        await sincronizar(con, nuevo)
    await auditar(request, admin, "grupo_editar", grupo["address"],
                  {k: datos[k] for k in ("name", "active", "allow_external") if k in datos})
    return dict(nuevo)


@router.delete("/{grupo_id}")
async def eliminar(grupo_id: int, request: Request, admin: dict = Depends(admin_actual)):
    grupo = await _grupo(request, admin, grupo_id)
    db = _db(request)
    async with db.acquire() as con, con.transaction():
        await con.execute("DELETE FROM alias WHERE address = $1", grupo["address"])
        await con.execute("DELETE FROM mail_group_members WHERE group_id = $1", grupo_id)
        await con.execute("DELETE FROM mail_groups WHERE id = $1", grupo_id)
    await auditar(request, admin, "grupo_eliminar", grupo["address"])
    return {"ok": True}


@router.post("/{grupo_id}/miembros", status_code=201)
async def agregar(grupo_id: int, request: Request, admin: dict = Depends(admin_actual)):
    grupo = await _grupo(request, admin, grupo_id)
    datos = await request.json()
    email = normalizar_direccion(datos.get("email"))
    if email == grupo["address"]:
        raise HTTPException(400, "Un grupo no puede ser miembro de sí mismo")
    db = _db(request)
    externo = not es_propio(admin, email)
    if externo and not grupo["allow_external"]:
        raise HTTPException(400, "Este grupo no admite miembros de fuera. Actívalo en el grupo si de verdad lo necesitas.")
    if not externo:
        if not await db.fetchval("SELECT 1 FROM alias WHERE address = $1", email):
            raise HTTPException(400, f"No existe en tu dominio: {email}")
        if await db.fetchval("SELECT 1 FROM mail_groups WHERE lower(address) = $1", email):
            raise HTTPException(400, "No se puede meter un grupo dentro de otro desde aquí")
    if await db.fetchval("SELECT count(*) FROM mail_group_members WHERE group_id = $1", grupo_id) >= MAX_MIEMBROS:
        raise HTTPException(400, f"Un grupo admite como máximo {MAX_MIEMBROS} miembros")
    if await db.fetchval("SELECT 1 FROM mail_group_members WHERE group_id = $1 AND lower(member_email) = $2", grupo_id, email):
        raise HTTPException(409, "Ya es miembro de este grupo")
    nombre = texto_limpio(datos.get("nombre")) or await db.fetchval(
        "SELECT COALESCE(name, '') FROM mailbox WHERE username = $1", email) or ""
    async with db.acquire() as con, con.transaction():
        nuevo = await con.fetchval(
            """INSERT INTO mail_group_members (group_id, member_email, member_name, can_send, receive)
               VALUES ($1, $2, $3, true, true) RETURNING id""", grupo_id, email, nombre)
        await sincronizar(con, grupo)
    await auditar(request, admin, "grupo_miembro_agregar", grupo["address"], {"miembro": email, "externo": externo})
    return {"id": nuevo, "email": email, "nombre": nombre, "recibe": True, "externo": externo}


@router.delete("/{grupo_id}/miembros/{miembro_id}")
async def quitar(grupo_id: int, miembro_id: int, request: Request, admin: dict = Depends(admin_actual)):
    grupo = await _grupo(request, admin, grupo_id)
    db = _db(request)
    async with db.acquire() as con, con.transaction():
        email = await con.fetchval(
            "DELETE FROM mail_group_members WHERE id = $1 AND group_id = $2 RETURNING member_email", miembro_id, grupo_id)
        if not email:
            raise HTTPException(404, "No encontrado")
        await sincronizar(con, grupo)
    await auditar(request, admin, "grupo_miembro_quitar", grupo["address"], {"miembro": email})
    return {"ok": True}
