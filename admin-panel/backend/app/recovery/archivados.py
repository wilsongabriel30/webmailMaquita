"""Papelera de recuperación: el correo que ya no está ni en la papelera del usuario.

Cuando alguien borra un correo, y más aún cuando vacía la papelera entera, el mensaje
desaparece de su buzón. Dovecot sí guarda una copia en una carpeta oculta del propio buzón
(plugin lazy_expunge), pero hasta ahora sacarla de ahí exigía entrar por SSH: cada petición de
«se me borró un correo» acababa en sistemas.

Esto pone esa recuperación en el panel. Solo lee y copia: la copia de seguridad nunca se toca,
así que se puede restaurar el mismo correo las veces que haga falta.

Es correo ajeno: entra por el mismo control que el resto de `recovery` (nunca un viewer) y
restaurar queda registrado en la auditoría con quién lo hizo.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_operador, require_role
from app.wrappers import doveadm

router = APIRouter(
    prefix="/api/recovery/archivados",
    tags=["recovery"],
    dependencies=[Depends(require_operador)],
)


async def _auditar(peticion, admin, accion, destinatario, detalles=None):
    await peticion.app.state.db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address)"
        " VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        admin["id"],
        admin["username"],
        accion,
        destinatario,
        json.dumps(detalles) if detalles else None,
        peticion.headers.get(
            "X-Real-IP", peticion.client.host if peticion.client else ""
        ),
    )


@router.get("/{username}/mensaje/{uid}")
async def ver(
    username: str,
    uid: str,
    admin: dict = Depends(get_current_admin),
):
    """El correo archivado entero, para confirmar que es el que piden antes de devolverlo."""
    try:
        mensaje = await doveadm.leer_archivado(username, uid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not mensaje.get("asunto") and not mensaje.get("cuerpo"):
        raise HTTPException(404, "Ese correo ya no está en el archivo")
    return mensaje


@router.get("/{username:path}")
async def listar(
    username: str,
    texto: str = "",
    admin: dict = Depends(get_current_admin),
):
    """Qué correos borrados se pueden recuperar de ese buzón.

    `texto` busca en el asunto y en el remitente, que es como la gente recuerda un correo.
    """
    try:
        mensajes = await doveadm.listar_archivados(username, texto.strip())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"buzon": username, "total": len(mensajes), "mensajes": mensajes}


@router.post("/restaurar")
async def restaurar(
    request: Request,
    admin: dict = Depends(require_role("superadmin", "admin")),
):
    """Devuelve el correo al buzón. Body: {buzon, uid, destino?}."""
    datos = await request.json()
    buzon = (datos.get("buzon") or "").strip()
    uid = str(datos.get("uid") or "").strip()
    destino = (datos.get("destino") or "INBOX").strip()
    if not buzon or not uid:
        raise HTTPException(400, "Hacen falta el buzón y el correo a recuperar")

    try:
        ok = await doveadm.restaurar_archivado(buzon, uid, destino)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(
            500, f"No se pudo devolver el correo. ¿Existe la carpeta «{destino}»?"
        )

    await _auditar(request, admin, "recuperar_correo_borrado", buzon, {"uid": uid, "destino": destino})
    return {"ok": True, "destino": destino}
