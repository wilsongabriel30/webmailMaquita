"""Favoritos, restaurar, eliminar permanente, vaciar papelera."""
from fastapi import APIRouter, Request, Depends, HTTPException
from app.auth.dependencies import get_current_user
from .helpers import audit

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.put("/{contact_id}/favorite")
async def toggle_favorite(contact_id: int, request: Request, username: str = Depends(get_current_user)):
    """Marca o desmarca como favorito."""
    body = await request.json()
    db = request.app.state.db_pool
    fav = body.get("favorite", True)
    r = await db.execute(
        "UPDATE user_contacts SET is_favorite=$3 WHERE id=$1 AND owner=$2 AND deleted_at IS NULL",
        contact_id, username, fav
    )
    if r == "UPDATE 0":
        raise HTTPException(404, "Contacto no encontrado")
    return {"status": "ok", "is_favorite": fav}


@router.post("/{contact_id}/restore")
async def restore_contact(contact_id: int, request: Request, username: str = Depends(get_current_user)):
    """Restaura un contacto de la papelera. Verifica dedup por email."""
    db = request.app.state.db_pool
    row = await db.fetchrow(
        "SELECT email FROM user_contacts WHERE id=$1 AND owner=$2 AND deleted_at IS NOT NULL",
        contact_id, username
    )
    if not row:
        raise HTTPException(404, "Contacto no encontrado en papelera")

    dup = await db.fetchval(
        "SELECT id FROM user_contacts WHERE owner=$1 AND LOWER(email)=LOWER($2) AND deleted_at IS NULL AND id!=$3",
        username, row["email"], contact_id
    )
    if dup:
        raise HTTPException(409, f"Ya existe un contacto activo con el email {row['email']}")

    await db.execute("UPDATE user_contacts SET deleted_at=NULL WHERE id=$1", contact_id)
    ip = request.client.host if request.client else ""
    await audit(db, username, contact_id, "restore", {}, ip)
    return {"status": "restored"}


@router.delete("/{contact_id}/permanent")
async def permanent_delete(contact_id: int, request: Request, username: str = Depends(get_current_user)):
    """Elimina permanentemente. Solo funciona con contactos ya en papelera."""
    db = request.app.state.db_pool
    r = await db.execute(
        "DELETE FROM user_contacts WHERE id=$1 AND owner=$2 AND deleted_at IS NOT NULL",
        contact_id, username
    )
    if r == "DELETE 0":
        raise HTTPException(404, "Solo se pueden eliminar permanentemente contactos en papelera")
    return {"status": "permanently_deleted"}


@router.delete("/trash")
async def empty_trash(request: Request, username: str = Depends(get_current_user)):
    """Vacía toda la papelera del usuario."""
    db = request.app.state.db_pool
    r = await db.execute("DELETE FROM user_contacts WHERE owner=$1 AND deleted_at IS NOT NULL", username)
    count = int(r.split()[-1]) if r else 0
    ip = request.client.host if request.client else ""
    await audit(db, username, None, "empty_trash", {"count": count}, ip)
    return {"status": "ok", "deleted_count": count}
