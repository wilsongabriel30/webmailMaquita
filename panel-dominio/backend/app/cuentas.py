"""Cuentas de correo de los dominios propios: ver, crear, editar, cambiar clave, activar o desactivar.

Lo que NO se hace desde aquí: eliminar cuentas ni leer correo. Eso es del administrador general.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.alcance import exigir_alcance
from app.claves import hash_buzon
from app.sesion import admin_actual, auditar
from app.validacion import cuota_permitida, exigir_clave_fuerte, normalizar_direccion, texto_limpio

router = APIRouter(prefix="/api/cuentas", tags=["cuentas"])
log = logging.getLogger("panel-dominio")



async def _cuenta(request: Request, admin: dict, username: str):
    username = str(username or "").strip().lower()
    exigir_alcance(admin, username)
    fila = await request.app.state.db.fetchrow("SELECT username, name, domain, quota, active, phone, email_other, created, modified FROM mailbox WHERE username = $1", username)
    if not fila:
        raise HTTPException(404, "No encontrado")
    return fila


@router.get("")
async def listar(request: Request, admin: dict = Depends(admin_actual)):
    filas = await request.app.state.db.fetch(
        "SELECT username, name, domain, quota, active, phone, email_other, created, modified FROM mailbox WHERE domain = ANY($1::varchar[]) ORDER BY domain, username",
        admin["dominios"],
    )
    return [dict(f) for f in filas]


@router.post("", status_code=201)
async def crear(request: Request, admin: dict = Depends(admin_actual)):
    datos = await request.json()
    username = normalizar_direccion(datos.get("username"))
    dominio = exigir_alcance(admin, username)
    clave = exigir_clave_fuerte(datos.get("password"), username)
    db = request.app.state.db

    dom = await db.fetchrow("SELECT active, mailboxes, maxquota FROM domain WHERE domain = $1", dominio)
    if not dom or not dom["active"]:
        raise HTTPException(400, "El dominio está desactivado")
    if dom["mailboxes"] and dom["mailboxes"] > 0:
        if await db.fetchval("SELECT count(*) FROM mailbox WHERE domain = $1", dominio) >= dom["mailboxes"]:
            raise HTTPException(400, f"El dominio llegó a su límite de {dom['mailboxes']} cuentas")
    if await db.fetchval("SELECT 1 FROM alias WHERE address = $1", username):
        raise HTTPException(409, "Esa dirección ya está en uso")

    cuota = cuota_permitida(datos.get("quota"), dom["maxquota"])
    local = username.split("@")[0]
    hash_clave = await hash_buzon(clave)
    try:
        async with db.acquire() as con, con.transaction():
            fila = await con.fetchrow(
                """INSERT INTO mailbox (username, password, name, maildir, quota, domain, local_part, active, phone, email_other)
                    VALUES ($1::varchar, $2::varchar, $3::varchar, $4::varchar, $5, $6::varchar, $7::varchar, true, $8, $9)
                    RETURNING username, name, domain, quota, active, phone, email_other, created, modified""",
                username, hash_clave, texto_limpio(datos.get("name")), f"{dominio}/{local}/", cuota,
                dominio, local, texto_limpio(datos.get("phone"), 50), texto_limpio(datos.get("email_other")),
            )
            await con.execute(
                "INSERT INTO alias (address, goto, domain, active) VALUES ($1::varchar,$1::varchar,$2::varchar,true)",
                username, dominio,
            )
    except Exception as e:
        if "duplicate key" in str(e):
            raise HTTPException(409, "Esa dirección ya está en uso")
        log.error("crear cuenta %s: %s", username, e)
        raise HTTPException(400, "No se pudo crear la cuenta")
    await auditar(request, admin, "cuenta_crear", username, {"cuota": cuota})
    return dict(fila)


@router.post("/{username:path}/clave")
async def cambiar_clave(username: str, request: Request, admin: dict = Depends(admin_actual)):
    fila = await _cuenta(request, admin, username)
    datos = await request.json()
    clave = exigir_clave_fuerte(datos.get("password"), fila["username"])
    await request.app.state.db.execute(
        "UPDATE mailbox SET password = $2, modified = NOW() WHERE username = $1",
        fila["username"], await hash_buzon(clave),
    )
    await auditar(request, admin, "cuenta_clave", fila["username"])
    return {"ok": True}


@router.post("/{username:path}/activa")
async def activar(username: str, request: Request, admin: dict = Depends(admin_actual)):
    fila = await _cuenta(request, admin, username)
    activa = bool((await request.json()).get("active"))
    await request.app.state.db.execute(
        "UPDATE mailbox SET active = $2, modified = NOW() WHERE username = $1", fila["username"], activa)
    await auditar(request, admin, "cuenta_activa", fila["username"], {"active": activa})
    return {"username": fila["username"], "active": activa}


@router.put("/{username:path}")
async def editar(username: str, request: Request, admin: dict = Depends(admin_actual)):
    fila = await _cuenta(request, admin, username)
    datos = await request.json()
    db = request.app.state.db
    maxima = await db.fetchval("SELECT maxquota FROM domain WHERE domain = $1", fila["domain"])
    cuota = cuota_permitida(datos.get("quota"), maxima or 0, actual=fila["quota"])
    nueva = await db.fetchrow(
        """UPDATE mailbox SET name = $2, quota = $3, phone = $4, email_other = $5, modified = NOW()
             WHERE username = $1 RETURNING username, name, domain, quota, active, phone, email_other, created, modified""",
        fila["username"],
        texto_limpio(datos["name"]) if "name" in datos else fila["name"],
        cuota,
        texto_limpio(datos["phone"], 50) if "phone" in datos else fila["phone"],
        texto_limpio(datos["email_other"]) if "email_other" in datos else fila["email_other"],
    )
    await auditar(request, admin, "cuenta_editar", fila["username"],
                  {k: datos[k] for k in ("name", "quota", "phone", "email_other") if k in datos})
    return dict(nueva)
