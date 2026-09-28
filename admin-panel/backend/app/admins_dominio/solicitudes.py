"""Solicitudes que llegan del portal de dominio. Hoy, una sola: eliminar una cuenta.

El portal no puede borrar buzones; los deja desactivados y pide el borrado. Aquí el
superadministrador lo confirma o lo rechaza. Rechazar reactiva la cuenta.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import require_superadmin
from app.mailboxes.limpieza_alias import quitar_de_destinos

router = APIRouter(prefix="/api/admins-dominio/solicitudes", tags=["admins-dominio"])


@router.get("")
async def listar(request: Request, admin: dict = Depends(require_superadmin)):
    filas = await request.app.state.db.fetch(
        """SELECT id, admin_username, tipo, objetivo, dominio, motivo, estado, resuelto_por, resuelto_en, creado_en
             FROM pd_solicitudes ORDER BY (estado = 'pendiente') DESC, creado_en DESC LIMIT 200""")
    return [dict(f) for f in filas]


@router.post("/{solicitud_id}/resolver")
async def resolver(solicitud_id: int, request: Request, admin: dict = Depends(require_superadmin)):
    aprobar = bool((await request.json()).get("aprobar"))
    db = request.app.state.db
    s = await db.fetchrow("SELECT * FROM pd_solicitudes WHERE id = $1", solicitud_id)
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    if s["estado"] != "pendiente":
        raise HTTPException(409, "Esa solicitud ya se resolvió")
    if s["tipo"] != "eliminar_cuenta":
        raise HTTPException(400, "Tipo de solicitud desconocido")
    cuenta = s["objetivo"]
    detalle = {"solicitud": solicitud_id, "pedida_por": s["admin_username"]}
    async with db.acquire() as con, con.transaction():
        if aprobar:
            detalle.update(await quitar_de_destinos(con, cuenta))
            await con.execute("DELETE FROM alias WHERE address = $1", cuenta)
            await con.execute("DELETE FROM mailbox WHERE username = $1", cuenta)
        else:
            await con.execute("UPDATE mailbox SET active = true, modified = NOW() WHERE username = $1", cuenta)
        await con.execute(
            "UPDATE pd_solicitudes SET estado = $2, resuelto_por = $3, resuelto_en = NOW() WHERE id = $1",
            solicitud_id, "aprobada" if aprobar else "rechazada", admin["username"])
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        admin["id"], admin["username"], "mailbox_delete" if aprobar else "solicitud_rechazada", cuenta,
        json.dumps(detalle), request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    return {"ok": True, "estado": "aprobada" if aprobar else "rechazada"}
