"""Acciones masivas — eliminar, favorito, categorizar múltiples contactos."""
from fastapi import APIRouter, Request, Depends
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.post("/bulk/delete")
async def bulk_delete(request: Request, username: str = Depends(get_current_user)):
    """Soft-delete masivo. Body: {contact_ids: [1,2,3]}."""
    body = await request.json()
    ids = body.get("contact_ids", [])
    if not ids:
        return {"status": "ok", "count": 0}
    db = request.app.state.db_pool
    r = await db.execute(
        "UPDATE user_contacts SET deleted_at=NOW() WHERE owner=$1 AND id=ANY($2::int[]) AND deleted_at IS NULL",
        username, ids
    )
    count = int(r.split()[-1]) if r else 0
    return {"status": "ok", "count": count}


@router.post("/bulk/favorite")
async def bulk_favorite(request: Request, username: str = Depends(get_current_user)):
    """Favorito masivo. Body: {contact_ids: [1,2,3], favorite: true/false}."""
    body = await request.json()
    ids = body.get("contact_ids", [])
    fav = body.get("favorite", True)
    db = request.app.state.db_pool
    r = await db.execute(
        "UPDATE user_contacts SET is_favorite=$3 WHERE owner=$1 AND id=ANY($2::int[]) AND deleted_at IS NULL",
        username, ids, fav
    )
    count = int(r.split()[-1]) if r else 0
    return {"status": "ok", "count": count}


@router.post("/bulk/category")
async def bulk_category(request: Request, username: str = Depends(get_current_user)):
    """Asigna categoría masiva. Body: {contact_ids: [1,2,3], category_id: 5}."""
    body = await request.json()
    ids = body.get("contact_ids", [])
    cat_id = body.get("category_id")
    if not ids or not cat_id:
        return {"status": "ok", "count": 0}
    db = request.app.state.db_pool
    # Verificar que la categoría pertenece al usuario
    cat_exists = await db.fetchval(
        "SELECT id FROM contact_categories WHERE id=$1 AND owner=$2", cat_id, username
    )
    if not cat_exists:
        from fastapi import HTTPException
        raise HTTPException(404, "Categoría no encontrada")
    # Solo asignar contactos que pertenecen al usuario
    owned = await db.fetch(
        "SELECT id FROM user_contacts WHERE id=ANY($1::int[]) AND owner=$2 AND deleted_at IS NULL",
        ids, username
    )
    owned_ids = [r["id"] for r in owned]
    for cid in owned_ids:
        await db.execute(
            "INSERT INTO contact_category_assignments (contact_id, category_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
            cid, cat_id
        )
    return {"status": "ok", "count": len(owned_ids)}
