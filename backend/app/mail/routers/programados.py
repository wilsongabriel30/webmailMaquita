"""«Programados»: ver, reprogramar, editar y cancelar los envíos programados (11/11/2026).

Programar un envío ya existía (`POST /api/mail/schedule`, lo envía `app/mail/programados.py`), pero
la persona no tenía dónde ver lo que había programado ni cómo cambiarlo. Estas rutas alimentan la
sección «Programados» de la interfaz. Se listan los pendientes y los que fallaron en los últimos días.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/mail/programados", tags=["mail-programados"])

DIAS_FALLIDOS = 7


class NuevaFecha(BaseModel):
    scheduled_at: str


def _lista(valor) -> list:
    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except ValueError:
            return []
    return list(valor or [])


def _resumen(r) -> dict:
    return {
        "id": r["id"],
        "to": _lista(r["to_list"]),
        "cc": _lista(r["cc_list"]),
        "bcc": _lista(r["bcc_list"]),
        "subject": r["subject"] or "",
        "scheduled_at": r["scheduled_at"].isoformat(),
        "status": r["status"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    }


def fecha_futura(texto: str) -> datetime:
    """Fecha ISO 8601 con zona, al menos un minuto en el futuro (400 si no)."""
    try:
        fecha = datetime.fromisoformat((texto or "").replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha no válida") from None
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    if (fecha - datetime.now(timezone.utc)).total_seconds() < 60:
        raise HTTPException(
            status_code=400, detail="La fecha de envío tiene que ser futura"
        )
    return fecha


@router.get("")
async def listar(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    filas = await db.fetch(
        f"""SELECT id, to_list, cc_list, bcc_list, subject, scheduled_at, status, created_at
              FROM scheduled_emails
             WHERE username = $1
               AND (status IN ('pending', 'sending')
                    OR (status = 'failed' AND scheduled_at > now() - interval '{DIAS_FALLIDOS} days'))
             ORDER BY scheduled_at ASC""",
        username,
    )
    return {"programados": [_resumen(f) for f in filas]}


@router.get("/{programado_id}")
async def detalle(
    programado_id: int, request: Request, username: str = Depends(get_current_user)
):
    """El correo completo, para volver a abrirlo en la redacción."""
    db = request.app.state.db_pool
    r = await db.fetchrow(
        """SELECT id, to_list, cc_list, bcc_list, subject, scheduled_at, status, created_at,
                  html_body, text_body, in_reply_to, "references"
             FROM scheduled_emails WHERE id = $1 AND username = $2""",
        programado_id,
        username,
    )
    if not r:
        raise HTTPException(status_code=404, detail="Envío programado no encontrado")
    return {
        **_resumen(r),
        "html_body": r["html_body"] or "",
        "text_body": r["text_body"] or "",
        "in_reply_to": r["in_reply_to"] or "",
        "references": r["references"] or "",
    }


@router.patch("/{programado_id}")
async def cambiar_fecha(
    programado_id: int,
    body: NuevaFecha,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Cambia la fecha de un envío pendiente (o reintenta uno que falló)."""
    fecha = fecha_futura(body.scheduled_at)
    db = request.app.state.db_pool
    r = await db.fetchrow(
        """UPDATE scheduled_emails SET scheduled_at = $3, status = 'pending'
            WHERE id = $1 AND username = $2 AND status IN ('pending', 'failed')
        RETURNING id, scheduled_at""",
        programado_id,
        username,
        fecha,
    )
    if not r:
        raise HTTPException(
            status_code=404, detail="Ese envío ya salió o fue cancelado"
        )
    return {"id": r["id"], "scheduled_at": r["scheduled_at"].isoformat()}


@router.delete("/{programado_id}")
async def cancelar(
    programado_id: int, request: Request, username: str = Depends(get_current_user)
):
    db = request.app.state.db_pool
    resultado = await db.execute(
        """UPDATE scheduled_emails SET status = 'cancelled'
            WHERE id = $1 AND username = $2 AND status IN ('pending', 'failed')""",
        programado_id,
        username,
    )
    if resultado == "UPDATE 0":
        raise HTTPException(
            status_code=404, detail="Ese envío ya salió o fue cancelado"
        )
    return {"status": "cancelled"}
