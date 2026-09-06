"""Listas de contactos (grupos) — CRUD + miembros + expand para compose."""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("/lists")
async def list_contact_lists(request: Request, username: str = Depends(get_current_user)):
    """Lista grupos del usuario con conteo de miembros activos."""
    db = request.app.state.db_pool
    rows = await db.fetch("""
        SELECT cl.*, COUNT(clm.contact_id) FILTER (WHERE uc.deleted_at IS NULL) AS member_count
        FROM contact_lists cl
        LEFT JOIN contact_list_members clm ON clm.list_id = cl.id
        LEFT JOIN user_contacts uc ON uc.id = clm.contact_id
        WHERE cl.owner = $1
        GROUP BY cl.id ORDER BY cl.name
    """, username)
    return [{"id": r["id"], "name": r["name"], "description": r["description"], "member_count": r["member_count"]} for r in rows]


@router.post("/lists")
async def create_list(request: Request, username: str = Depends(get_current_user)):
    """Crea un grupo. Nombre único por usuario."""
    body = await request.json()
    db = request.app.state.db_pool
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Nombre requerido")
    try:
        row = await db.fetchrow(
            "INSERT INTO contact_lists (owner, name, description) VALUES ($1,$2,$3) RETURNING id",
            username, name, body.get("description", "")
        )
    except Exception:
        raise HTTPException(409, "Ya existe una lista con ese nombre")
    return {"status": "created", "id": row["id"]}


@router.put("/lists/{list_id}")
async def update_list(list_id: int, request: Request, username: str = Depends(get_current_user)):
    """Actualiza nombre y/o descripción de un grupo."""
    body = await request.json()
    db = request.app.state.db_pool
    await db.execute(
        "UPDATE contact_lists SET name=COALESCE($3, name), description=COALESCE($4, description) WHERE id=$1 AND owner=$2",
        list_id, username, body.get("name"), body.get("description")
    )
    return {"status": "updated"}


@router.delete("/lists/{list_id}")
async def delete_list(list_id: int, request: Request, username: str = Depends(get_current_user)):
    """Elimina grupo (CASCADE borra miembros automáticamente)."""
    db = request.app.state.db_pool
    await db.execute("DELETE FROM contact_lists WHERE id=$1 AND owner=$2", list_id, username)
    return {"status": "deleted"}


@router.get("/lists/{list_id}/members")
async def list_members(list_id: int, request: Request, username: str = Depends(get_current_user)):
    """Lista miembros activos de un grupo."""
    db = request.app.state.db_pool
    rows = await db.fetch("""
        SELECT uc.id, uc.display_name, uc.email, uc.phone, uc.organization, uc.is_favorite
        FROM contact_list_members clm
        JOIN user_contacts uc ON uc.id = clm.contact_id AND uc.deleted_at IS NULL
        WHERE clm.list_id = $1 AND uc.owner = $2
        ORDER BY uc.display_name
    """, list_id, username)
    return [dict(r) for r in rows]


@router.post("/lists/{list_id}/members")
async def add_members(list_id: int, request: Request, username: str = Depends(get_current_user)):
    """Agrega contactos a un grupo. Body: {contact_ids: [1,2,3]}."""
    body = await request.json()
    db = request.app.state.db_pool
    contact_ids = body.get("contact_ids", [])

    exists = await db.fetchval("SELECT id FROM contact_lists WHERE id=$1 AND owner=$2", list_id, username)
    if not exists:
        raise HTTPException(404, "Lista no encontrada")

    # Verificar que los contactos pertenecen al usuario
    owned = await db.fetch(
        "SELECT id FROM user_contacts WHERE id=ANY($1::int[]) AND owner=$2 AND deleted_at IS NULL",
        contact_ids, username
    )
    owned_ids = [r["id"] for r in owned]
    added = 0
    for cid in owned_ids:
        try:
            await db.execute(
                "INSERT INTO contact_list_members (list_id, contact_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                list_id, cid
            )
            added += 1
        except Exception:
            pass
    return {"status": "ok", "added": added}


@router.delete("/lists/{list_id}/members/{cid}")
async def remove_member(list_id: int, cid: int, request: Request, username: str = Depends(get_current_user)):
    """Quita un contacto de un grupo."""
    db = request.app.state.db_pool
    # Verificar que la lista pertenece al usuario
    exists = await db.fetchval("SELECT id FROM contact_lists WHERE id=$1 AND owner=$2", list_id, username)
    if not exists:
        raise HTTPException(404, "Lista no encontrada")
    await db.execute("DELETE FROM contact_list_members WHERE list_id=$1 AND contact_id=$2", list_id, cid)
    return {"status": "removed"}


@router.get("/lists/{list_id}/expand")
async def expand_list(list_id: int, request: Request, username: str = Depends(get_current_user)):
    """Retorna emails de miembros para usar como destinatarios en compose."""
    db = request.app.state.db_pool
    rows = await db.fetch("""
        SELECT uc.display_name, uc.email
        FROM contact_list_members clm
        JOIN user_contacts uc ON uc.id = clm.contact_id AND uc.deleted_at IS NULL
        WHERE clm.list_id = $1 AND uc.owner = $2
        ORDER BY uc.display_name
    """, list_id, username)
    return [{"name": r["display_name"], "email": r["email"]} for r in rows]
