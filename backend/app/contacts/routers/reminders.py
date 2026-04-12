"""Recordatorios — CRUD de reminders para contactos."""
from fastapi import APIRouter, Request, Depends, HTTPException
from app.auth.dependencies import get_current_user
from .helpers import audit

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


def reminder_to_dict(row) -> dict:
    d = dict(row)
    for k in ("due_date", "created_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
    return d


@router.get("/reminders")
async def list_all_reminders(request: Request, username: str = Depends(get_current_user)):
    """Lista todos los reminders pendientes del usuario, ordenados por fecha."""
    db = request.app.state.db_pool
    rows = await db.fetch(
        "SELECT cr.*, uc.display_name AS contact_name, uc.email AS contact_email "
        "FROM contact_reminders cr "
        "JOIN user_contacts uc ON uc.id = cr.contact_id "
        "WHERE cr.owner=$1 "
        "ORDER BY cr.completed ASC, cr.due_date ASC",
        username
    )
    result = []
    for r in rows:
        d = reminder_to_dict(r)
        d["contact_name"] = r["contact_name"]
        d["contact_email"] = r["contact_email"]
        result.append(d)
    return result


@router.get("/{contact_id}/reminders")
async def list_contact_reminders(contact_id: int, request: Request, username: str = Depends(get_current_user)):
    """Reminders de un contacto específico."""
    db = request.app.state.db_pool
    # Verificar que el contacto pertenece al usuario
    exists = await db.fetchval(
        "SELECT id FROM user_contacts WHERE id=$1 AND owner=$2", contact_id, username
    )
    if not exists:
        raise HTTPException(404, "Contacto no encontrado")

    rows = await db.fetch(
        "SELECT * FROM contact_reminders WHERE contact_id=$1 AND owner=$2 ORDER BY completed ASC, due_date ASC",
        contact_id, username
    )
    return [reminder_to_dict(r) for r in rows]


@router.post("/{contact_id}/reminders")
async def create_reminder(contact_id: int, request: Request, username: str = Depends(get_current_user)):
    """Crea un reminder para un contacto."""
    body = await request.json()
    db = request.app.state.db_pool
    title = body.get("title", "").strip()
    description = body.get("description", "")
    due_date = body.get("due_date")

    if not title:
        raise HTTPException(400, "Título requerido")
    if not due_date:
        raise HTTPException(400, "Fecha requerida")

    exists = await db.fetchval(
        "SELECT id FROM user_contacts WHERE id=$1 AND owner=$2", contact_id, username
    )
    if not exists:
        raise HTTPException(404, "Contacto no encontrado")

    row = await db.fetchrow(
        "INSERT INTO contact_reminders (owner, contact_id, title, description, due_date) "
        "VALUES ($1,$2,$3,$4,$5::timestamptz) RETURNING *",
        username, contact_id, title, description, due_date
    )
    await audit(db, username, contact_id, "reminder_created", {"title": title})
    return reminder_to_dict(row)


@router.put("/reminders/{reminder_id}")
async def update_reminder(reminder_id: int, request: Request, username: str = Depends(get_current_user)):
    """Actualiza un reminder."""
    body = await request.json()
    db = request.app.state.db_pool

    existing = await db.fetchrow(
        "SELECT * FROM contact_reminders WHERE id=$1 AND owner=$2", reminder_id, username
    )
    if not existing:
        raise HTTPException(404, "Reminder no encontrado")

    title = body.get("title", existing["title"])
    description = body.get("description", existing["description"])
    due_date = body.get("due_date")

    await db.execute(
        "UPDATE contact_reminders SET title=$2, description=$3, due_date=COALESCE($4::timestamptz, due_date) WHERE id=$1",
        reminder_id, title, description, due_date
    )
    updated = await db.fetchrow("SELECT * FROM contact_reminders WHERE id=$1", reminder_id)
    return reminder_to_dict(updated)


@router.delete("/reminders/{reminder_id}")
async def delete_reminder(reminder_id: int, request: Request, username: str = Depends(get_current_user)):
    """Elimina un reminder."""
    db = request.app.state.db_pool
    existing = await db.fetchrow(
        "SELECT * FROM contact_reminders WHERE id=$1 AND owner=$2", reminder_id, username
    )
    if not existing:
        raise HTTPException(404, "Reminder no encontrado")

    await db.execute("DELETE FROM contact_reminders WHERE id=$1", reminder_id)
    await audit(db, username, existing["contact_id"], "reminder_deleted", {"title": existing["title"]})
    return {"status": "deleted"}


@router.put("/reminders/{reminder_id}/complete")
async def complete_reminder(reminder_id: int, request: Request, username: str = Depends(get_current_user)):
    """Marca/desmarca un reminder como completado."""
    db = request.app.state.db_pool
    existing = await db.fetchrow(
        "SELECT * FROM contact_reminders WHERE id=$1 AND owner=$2", reminder_id, username
    )
    if not existing:
        raise HTTPException(404, "Reminder no encontrado")

    new_status = not existing["completed"]
    await db.execute(
        "UPDATE contact_reminders SET completed=$2 WHERE id=$1",
        reminder_id, new_status
    )
    updated = await db.fetchrow("SELECT * FROM contact_reminders WHERE id=$1", reminder_id)
    return reminder_to_dict(updated)
