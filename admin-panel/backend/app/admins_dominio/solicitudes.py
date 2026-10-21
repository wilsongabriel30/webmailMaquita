"""Solicitudes que llegan del portal de dominio: eliminar una cuenta o dar de baja un sitio web.

- eliminar_cuenta: el portal no puede borrar buzones; los deja desactivados y pide el borrado.
  Rechazar reactiva la cuenta.
- baja_sitio: el portal no puede borrar sitios ni los desactiva al pedirlo. Confirmar llama a
  maquita-sitios borrar por el mismo camino que «Hospedaje → Sitios web» (archivos y bases a la
  papelera, registros DNS fuera); rechazar solo cierra la solicitud.
Aquí el superadministrador lo confirma o lo rechaza.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import require_superadmin
from app.mailboxes.limpieza_alias import quitar_de_destinos

router = APIRouter(prefix="/api/admins-dominio/solicitudes", tags=["admins-dominio"])
TIPOS = ("eliminar_cuenta", "baja_sitio")


@router.get("")
async def listar(request: Request, admin: dict = Depends(require_superadmin)):
    filas = await request.app.state.db.fetch(
        """SELECT id, admin_username, tipo, objetivo, dominio, motivo, estado, resuelto_por, resuelto_en, creado_en
             FROM pd_solicitudes ORDER BY (estado = 'pendiente') DESC, creado_en DESC LIMIT 200""")
    return [dict(f) for f in filas]


async def _baja_sitio(request: Request, admin: dict, s) -> dict:
    """Comprueba que el sitio sigue colgando del dominio de la solicitud y lo da de baja."""
    from app.sitios.router import _dominio, dar_de_baja

    sitio, dominio = _dominio(s["objetivo"]), (s["dominio"] or "").strip().lower()
    if not (sitio == dominio or sitio.endswith("." + dominio)):
        raise HTTPException(400, "El sitio de la solicitud no pertenece a su dominio")
    return await dar_de_baja(request, admin, sitio, {"solicitud": s["id"], "pedida_por": s["admin_username"]})


async def _cerrar(con, solicitud_id: int, aprobar: bool, quien: str):
    await con.execute(
        "UPDATE pd_solicitudes SET estado = $2, resuelto_por = $3, resuelto_en = NOW() WHERE id = $1 AND estado = 'pendiente'",
        solicitud_id, "aprobada" if aprobar else "rechazada", quien)


@router.post("/{solicitud_id}/resolver")
async def resolver(solicitud_id: int, request: Request, admin: dict = Depends(require_superadmin)):
    aprobar = bool((await request.json()).get("aprobar"))
    db = request.app.state.db
    s = await db.fetchrow("SELECT * FROM pd_solicitudes WHERE id = $1", solicitud_id)
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    if s["estado"] != "pendiente":
        raise HTTPException(409, "Esa solicitud ya se resolvió")
    if s["tipo"] not in TIPOS:
        raise HTTPException(400, "Tipo de solicitud desconocido")
    objetivo = s["objetivo"]
    detalle = {"solicitud": solicitud_id, "pedida_por": s["admin_username"]}
    if s["tipo"] == "baja_sitio":
        # Si maquita-sitios falla, la solicitud sigue pendiente (el error llega a la pantalla).
        resultado = await _baja_sitio(request, admin, s) if aprobar else None
        await _cerrar(db, solicitud_id, aprobar, admin["username"])
        if not aprobar:
            await _auditar(request, admin, "solicitud_rechazada", objetivo, detalle)
        return {"ok": True, "estado": "aprobada" if aprobar else "rechazada",
                **({"papelera": resultado.get("papelera")} if resultado else {})}
    async with db.acquire() as con, con.transaction():
        if aprobar:
            detalle.update(await quitar_de_destinos(con, objetivo))
            await con.execute("DELETE FROM alias WHERE address = $1", objetivo)
            await con.execute("DELETE FROM mailbox WHERE username = $1", objetivo)
        else:
            await con.execute("UPDATE mailbox SET active = true, modified = NOW() WHERE username = $1", objetivo)
        await _cerrar(con, solicitud_id, aprobar, admin["username"])
    await _auditar(request, admin, "mailbox_delete" if aprobar else "solicitud_rechazada", objetivo, detalle)
    return {"ok": True, "estado": "aprobada" if aprobar else "rechazada"}


async def _auditar(request: Request, admin: dict, accion: str, objetivo: str, detalle: dict):
    await request.app.state.db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        admin["id"], admin["username"], accion, objetivo,
        json.dumps(detalle), request.headers.get("X-Real-IP", request.client.host if request.client else ""))
