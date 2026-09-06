"""Crear contacto desde un correo recibido."""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.post("/from-email")
async def create_from_email(request: Request, username: str = Depends(get_current_user)):
    """
    Crea contacto rápido desde MessageView. Body: {name, email}.
    Si ya existe, retorna el id existente.
    """
    body = await request.json()
    email = body.get("email", "").strip()
    name = body.get("name", "").strip()
    if not email:
        raise HTTPException(400, "Email requerido")

    db = request.app.state.db_pool
    existing = await db.fetchval(
        "SELECT id FROM user_contacts WHERE owner=$1 AND LOWER(email)=LOWER($2) AND deleted_at IS NULL",
        username, email
    )
    if existing:
        return {"status": "exists", "id": existing}

    row = await db.fetchrow(
        "INSERT INTO user_contacts (owner, display_name, email, source) VALUES ($1,$2,$3,'from_email') RETURNING id",
        username, name, email
    )
    return {"status": "created", "id": row["id"]}
