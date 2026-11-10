"""Labels router — user label/tag system for messages."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.mail.services.etiquetas_faltantes import (
    contar_vigentes,
    contar_vigentes_por_etiqueta,
    limpiar_faltantes_vistos,
)
from app.mail.services.etiquetas_predeterminadas import PREDETERMINADAS, crear_si_no_hay

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mail", tags=["mail-labels"])

# Se conserva el nombre por compatibilidad; la lista vive en services/etiquetas_predeterminadas.py.
DEFAULT_LABELS = list(PREDETERMINADAS)


async def ensure_tables(db):
    # Tablas creadas por migrations/init_tables.sql (Fase 3)
    # user_labels, message_labels + índices
    pass


async def seed_defaults(db, owner: str):
    """Crea las etiquetas predeterminadas si la cuenta no tiene ninguna.

    Ya NO lo llama `GET /labels` (un GET no debe escribir, 09/11/2026): lo hace
    `POST /labels/predeterminadas`, que el navegador pide una vez si la lista llega vacía.
    """
    return await crear_si_no_hay(db, owner)


class LabelCreate(BaseModel):
    name: str
    color: str = "#0078d4"


class LabelUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


class AssignBody(BaseModel):
    folder: str
    uids: list[int]


@router.get("/labels")
async def list_labels(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    await ensure_tables(db)
    rows = await db.fetch(
        "SELECT id, name, color, created_at FROM user_labels WHERE owner = $1 ORDER BY id",
        username,
    )
    # Contador = asignaciones vigentes (las marcadas faltantes no cuentan), en una sola consulta.
    conteos = await contar_vigentes_por_etiqueta(db, username)
    labels = [
        {
            "id": r["id"],
            "name": r["name"],
            "color": r["color"],
            "count": conteos.get(r["id"], 0),
        }
        for r in rows
    ]
    return {"labels": labels}


@router.post("/labels/predeterminadas")
async def crear_predeterminadas(
    request: Request, username: str = Depends(get_current_user)
):
    """Crea las 5 etiquetas predeterminadas solo si la cuenta no tiene ninguna. Idempotente."""
    db = request.app.state.db_pool
    creadas = await crear_si_no_hay(db, username)
    return {"creadas": creadas}


@router.post("/labels")
async def create_label(
    body: LabelCreate, request: Request, username: str = Depends(get_current_user)
):
    db = request.app.state.db_pool
    await ensure_tables(db)
    try:
        row = await db.fetchrow(
            "INSERT INTO user_labels (owner, name, color) VALUES ($1, $2, $3) RETURNING id, name, color",
            username,
            body.name.strip(),
            body.color,
        )
        return {"id": row["id"], "name": row["name"], "color": row["color"]}
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Label already exists")
        raise


@router.put("/labels/{label_id}")
async def update_label(
    label_id: int,
    body: LabelUpdate,
    request: Request,
    username: str = Depends(get_current_user),
):
    db = request.app.state.db_pool
    await ensure_tables(db)
    existing = await db.fetchrow(
        "SELECT id FROM user_labels WHERE id = $1 AND owner = $2",
        label_id,
        username,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Label not found")
    if body.name is not None:
        await db.execute(
            "UPDATE user_labels SET name = $1 WHERE id = $2 AND owner = $3",
            body.name.strip(),
            label_id,
            username,
        )
    if body.color is not None:
        await db.execute(
            "UPDATE user_labels SET color = $1 WHERE id = $2 AND owner = $3",
            body.color,
            label_id,
            username,
        )
    row = await db.fetchrow(
        "SELECT id, name, color FROM user_labels WHERE id = $1 AND owner = $2",
        label_id,
        username,
    )
    return {"id": row["id"], "name": row["name"], "color": row["color"]}


@router.delete("/labels/{label_id}")
async def delete_label(
    label_id: int, request: Request, username: str = Depends(get_current_user)
):
    db = request.app.state.db_pool
    await ensure_tables(db)
    result = await db.execute(
        "DELETE FROM user_labels WHERE id = $1 AND owner = $2",
        label_id,
        username,
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Label not found")
    return {"ok": True}


@router.post("/labels/{label_id}/assign")
async def assign_label(
    label_id: int,
    body: AssignBody,
    request: Request,
    username: str = Depends(get_current_user),
):
    db = request.app.state.db_pool
    await ensure_tables(db)
    # Verify label belongs to user
    lbl = await db.fetchrow(
        "SELECT id FROM user_labels WHERE id = $1 AND owner = $2", label_id, username
    )
    if not lbl:
        raise HTTPException(status_code=404, detail="Label not found")
    count = 0
    for uid in body.uids:
        try:
            await db.execute(
                "INSERT INTO message_labels (owner, folder, message_uid, label_id) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                username,
                body.folder,
                uid,
                label_id,
            )
            count += 1
        except Exception:
            pass
    return {"assigned": count}


@router.post("/labels/{label_id}/unassign")
async def unassign_label(
    label_id: int,
    body: AssignBody,
    request: Request,
    username: str = Depends(get_current_user),
):
    db = request.app.state.db_pool
    await ensure_tables(db)
    count = 0
    for uid in body.uids:
        result = await db.execute(
            "DELETE FROM message_labels WHERE owner = $1 AND folder = $2 AND message_uid = $3 AND label_id = $4",
            username,
            body.folder,
            uid,
            label_id,
        )
        if result != "DELETE 0":
            count += 1
    return {"unassigned": count}


@router.get("/labels/messages/{folder}")
async def get_message_labels(
    folder: str,
    request: Request,
    uids: str = Query(...),
    username: str = Depends(get_current_user),
):
    db = request.app.state.db_pool
    await ensure_tables(db)
    uid_list = [int(u.strip()) for u in uids.split(",") if u.strip().isdigit()]
    if not uid_list:
        return {"message_labels": {}}
    # Estos uids se están viendo en su carpeta: si alguna asignación estaba marcada faltante, ya no lo es.
    try:
        await limpiar_faltantes_vistos(db, username, folder, uid_list)
    except (
        Exception
    ) as e:  # columna aún sin migrar u otro fallo: las etiquetas se muestran igual
        logger.debug(
            "etiquetas: no se pudo limpiar faltantes de %s/%s: %s", username, folder, e
        )
    rows = await db.fetch(
        """
        SELECT ml.message_uid, ml.label_id, ul.name, ul.color
        FROM message_labels ml
        JOIN user_labels ul ON ul.id = ml.label_id
        WHERE ml.owner = $1 AND ml.folder = $2 AND ml.message_uid = ANY($3::int[])
    """,
        username,
        folder,
        uid_list,
    )
    result: dict = {}
    for r in rows:
        uid_key = str(r["message_uid"])
        if uid_key not in result:
            result[uid_key] = []
        result[uid_key].append(
            {"id": r["label_id"], "name": r["name"], "color": r["color"]}
        )
    return {"message_labels": result}


@router.get("/labels/{label_id}/messages")
async def get_label_messages(
    label_id: int,
    request: Request,
    username: str = Depends(get_current_user),
    page: int = 1,
    per_page: int = 50,
):
    """Get messages that have a specific label (for sidebar label click)."""
    db = request.app.state.db_pool
    await ensure_tables(db)
    lbl = await db.fetchrow(
        "SELECT id, name, color FROM user_labels WHERE id = $1 AND owner = $2",
        label_id,
        username,
    )
    if not lbl:
        raise HTTPException(status_code=404, detail="Label not found")
    total = await contar_vigentes(db, username, label_id)
    offset = (page - 1) * per_page
    rows = await db.fetch(
        "SELECT folder, message_uid FROM message_labels WHERE label_id = $1 AND owner = $2 AND faltante_desde IS NULL ORDER BY created_at DESC LIMIT $3 OFFSET $4",
        label_id,
        username,
        per_page,
        offset,
    )
    return {
        "label": {"id": lbl["id"], "name": lbl["name"], "color": lbl["color"]},
        "total": total,
        "messages": [{"folder": r["folder"], "uid": r["message_uid"]} for r in rows],
    }
