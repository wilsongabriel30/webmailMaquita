"""Categorías — CRUD + asignación a contactos."""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("/categories")
async def list_categories(request: Request, username: str = Depends(get_current_user)):
    """Lista categorías del usuario con conteo de contactos activos."""
    db = request.app.state.db_pool
    rows = await db.fetch("""
        SELECT cc.*, COUNT(cca.contact_id) AS contact_count
        FROM contact_categories cc
        LEFT JOIN contact_category_assignments cca ON cca.category_id = cc.id
        LEFT JOIN user_contacts uc ON uc.id = cca.contact_id AND uc.deleted_at IS NULL
        WHERE cc.owner = $1
        GROUP BY cc.id ORDER BY cc.name
    """, username)
    return [{"id": r["id"], "name": r["name"], "color": r["color"], "contact_count": r["contact_count"]} for r in rows]


@router.post("/categories")
async def create_category(request: Request, username: str = Depends(get_current_user)):
    """Crea una categoría. Nombre único por usuario."""
    body = await request.json()
    db = request.app.state.db_pool
    name = body.get("name", "").strip()
    color = body.get("color", "#0078d4")
    if not name:
        raise HTTPException(400, "Nombre requerido")
    try:
        row = await db.fetchrow(
            "INSERT INTO contact_categories (owner, name, color) VALUES ($1,$2,$3) RETURNING id",
            username, name, color
        )
    except Exception:
        raise HTTPException(409, "Ya existe una categoría con ese nombre")
    return {"status": "created", "id": row["id"]}


@router.put("/categories/{cat_id}")
async def update_category(cat_id: int, request: Request, username: str = Depends(get_current_user)):
    """Actualiza nombre y/o color de una categoría."""
    body = await request.json()
    db = request.app.state.db_pool
    await db.execute(
        "UPDATE contact_categories SET name=COALESCE($3, name), color=COALESCE($4, color) WHERE id=$1 AND owner=$2",
        cat_id, username, body.get("name"), body.get("color")
    )
    return {"status": "updated"}


@router.delete("/categories/{cat_id}")
async def delete_category(cat_id: int, request: Request, username: str = Depends(get_current_user)):
    """Elimina categoría y desasigna de todos los contactos."""
    db = request.app.state.db_pool
    # Verificar que la categoría pertenece al usuario antes de eliminar
    exists = await db.fetchval("SELECT id FROM contact_categories WHERE id=$1 AND owner=$2", cat_id, username)
    if not exists:
        raise HTTPException(404, "Categoría no encontrada")
    await db.execute("DELETE FROM contact_category_assignments WHERE category_id=$1", cat_id)
    await db.execute("DELETE FROM contact_categories WHERE id=$1 AND owner=$2", cat_id, username)
    return {"status": "deleted"}


@router.put("/{contact_id}/categories")
async def assign_categories(contact_id: int, request: Request, username: str = Depends(get_current_user)):
    """Reemplaza todas las categorías de un contacto. Body: {category_ids: [1,2,3]}."""
    body = await request.json()
    db = request.app.state.db_pool
    cat_ids = body.get("category_ids", [])

    exists = await db.fetchval("SELECT id FROM user_contacts WHERE id=$1 AND owner=$2", contact_id, username)
    if not exists:
        raise HTTPException(404, "Contacto no encontrado")

    await db.execute("DELETE FROM contact_category_assignments WHERE contact_id=$1", contact_id)
    for cid in cat_ids:
        await db.execute(
            "INSERT INTO contact_category_assignments (contact_id, category_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
            contact_id, cid
        )
    return {"status": "ok"}
