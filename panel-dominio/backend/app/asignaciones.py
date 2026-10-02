"""Cuentas asignadas (multicuenta): qué cuentas puede abrir cada persona en su webmail.

Se guarda en `mail_delegation` (mailbox = la cuenta asignada, delegate = la persona). El webmail
comprueba la asignación en cada petición: quitarla corta el acceso al instante.

Alcance: la cuenta Y la persona tienen que ser de dominios del administrador. Quien administra
varios dominios puede cruzarlos (una cuenta de uno para una persona de otro), pero nunca tocar
un dominio que no administra. Las asignaciones con un extremo fuera de su alcance no se le
muestran.

`completo` = leer, enviar como esa cuenta y gestionarla. Sin él, solo lectura.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.alcance import exigir_alcance
from app.sesion import admin_actual, auditar
from app.validacion import normalizar_direccion

router = APIRouter(prefix="/api/asignaciones", tags=["asignaciones"])

_SELECT = """SELECT d.id, lower(d.mailbox) AS cuenta, lower(d.delegate) AS persona,
                    COALESCE(d.can_send_as, false) AS completo, d.created_at,
                    mc.name AS nombre_cuenta, mp.name AS nombre_persona
               FROM mail_delegation d
               LEFT JOIN mailbox mc ON mc.username = lower(d.mailbox)
               LEFT JOIN mailbox mp ON mp.username = lower(d.delegate)
              WHERE split_part(lower(d.mailbox), '@', 2) = ANY($1::varchar[])
                AND split_part(lower(d.delegate), '@', 2) = ANY($1::varchar[])"""


def par_valido(admin: dict, cuenta, persona) -> tuple[str, str]:
    """Normaliza y comprueba el alcance de los dos extremos. Ajeno → 404, como en el resto."""
    cuenta, persona = normalizar_direccion(cuenta), normalizar_direccion(persona)
    exigir_alcance(admin, cuenta)
    exigir_alcance(admin, persona)
    if cuenta == persona:
        raise HTTPException(400, "Una persona no necesita que le asignen su propia cuenta")
    return cuenta, persona


def _fila(f) -> dict:
    datos = dict(f)
    datos["created_at"] = f["created_at"].isoformat() if f["created_at"] else None
    return datos


async def _en_alcance(request: Request, admin: dict, id_: int):
    fila = await request.app.state.db.fetchrow(_SELECT + " AND d.id = $2", admin["dominios"], id_)
    if not fila:
        raise HTTPException(404, "No encontrado")
    return fila


@router.get("")
async def listar(request: Request, admin: dict = Depends(admin_actual)):
    filas = await request.app.state.db.fetch(_SELECT + " ORDER BY persona, cuenta", admin["dominios"])
    return [_fila(f) for f in filas]


@router.post("", status_code=201)
async def asignar(request: Request, admin: dict = Depends(admin_actual)):
    datos = await request.json()
    cuenta, persona = par_valido(admin, datos.get("cuenta"), datos.get("persona"))
    completo = bool(datos.get("completo", True))
    db = request.app.state.db
    activas = await db.fetch("SELECT username FROM mailbox WHERE username = ANY($1::varchar[]) AND active = true",
                             [cuenta, persona])
    activas = {f["username"] for f in activas}
    if cuenta not in activas:
        raise HTTPException(400, f"La cuenta {cuenta} no existe o está desactivada")
    if persona not in activas:
        raise HTTPException(400, f"La persona {persona} no tiene una cuenta activa")
    # El webmail nunca abre la cuenta de un administrador general; no se deja asignarla.
    if await db.fetchval("SELECT 1 FROM admin WHERE lower(username) = $1 AND superadmin = true", cuenta):
        raise HTTPException(400, "Esa cuenta no se puede asignar")
    antes = await db.fetchrow(
        "SELECT id, COALESCE(can_send_as, false) AS completo FROM mail_delegation WHERE lower(mailbox) = $1 AND lower(delegate) = $2",
        cuenta, persona)
    if antes:
        await db.execute("UPDATE mail_delegation SET can_send_as = $2 WHERE id = $1", antes["id"], completo)
        id_ = antes["id"]
    else:
        id_ = await db.fetchval(
            "INSERT INTO mail_delegation (mailbox, delegate, can_send_as) VALUES ($1, $2, $3) RETURNING id",
            cuenta, persona, completo)
    await auditar(request, admin, "asignacion_guardar", cuenta,
                  {"persona": persona, "completo": completo, "antes": antes["completo"] if antes else None})
    return _fila(await _en_alcance(request, admin, id_))


@router.put("/{id_}")
async def cambiar_permiso(id_: int, request: Request, admin: dict = Depends(admin_actual)):
    fila = await _en_alcance(request, admin, id_)
    completo = bool((await request.json()).get("completo", True))
    await request.app.state.db.execute("UPDATE mail_delegation SET can_send_as = $2 WHERE id = $1", id_, completo)
    await auditar(request, admin, "asignacion_permiso", fila["cuenta"],
                  {"persona": fila["persona"], "completo": completo, "antes": fila["completo"]})
    return _fila(await _en_alcance(request, admin, id_))


@router.delete("/{id_}")
async def quitar(id_: int, request: Request, admin: dict = Depends(admin_actual)):
    fila = await _en_alcance(request, admin, id_)
    await request.app.state.db.execute("DELETE FROM mail_delegation WHERE id = $1", id_)
    await auditar(request, admin, "asignacion_quitar", fila["cuenta"], {"persona": fila["persona"], "completo": fila["completo"]})
    return {"ok": True}
