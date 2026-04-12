"""
Notas colaborativas — notas compartidas sobre contactos visibles para todo el dominio.
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


class NoteCreate(BaseModel):
    content: str
    tags: list[str] = []
    org_contact_id: Optional[int] = None
    contact_id: Optional[int] = None


class NoteUpdate(BaseModel):
    content: str
    tags: list[str] = []


def _get_domain(user: str) -> str:
    if "@" in user:
        return user.split("@")[1]
    return user


@router.get("/{contact_id}/shared-notes")
async def get_shared_notes(request: Request, contact_id: int, username: str = Depends(get_current_user)):
    """Obtener notas compartidas de un contacto personal."""
    db = request.app.state.db_pool
    user = username

    # Verificar que el contacto pertenece al mismo dominio
    contact = await db.fetchrow(
        "SELECT owner FROM user_contacts WHERE id = $1", contact_id
    )
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")

    domain = _get_domain(user)
    contact_domain = _get_domain(contact["owner"])
    if domain != contact_domain:
        raise HTTPException(403, "No tiene acceso a las notas de este contacto")

    rows = await db.fetch(
        """SELECT id, contact_id, org_contact_id, author, content, tags, created_at, updated_at
           FROM contact_shared_notes
           WHERE contact_id = $1
           ORDER BY created_at DESC""",
        contact_id,
    )
    return [dict(r) for r in rows]


@router.get("/directory/{org_contact_id}/shared-notes")
async def get_org_shared_notes(request: Request, org_contact_id: int, username: str = Depends(get_current_user)):
    """Obtener notas compartidas de un contacto del directorio."""
    db = request.app.state.db_pool
    user = username
    domain = _get_domain(user)

    org = await db.fetchrow(
        "SELECT domain FROM org_contacts WHERE id = $1", org_contact_id
    )
    if not org or org["domain"] != domain:
        raise HTTPException(404, "Contacto no encontrado en directorio")

    rows = await db.fetch(
        """SELECT id, contact_id, org_contact_id, author, content, tags, created_at, updated_at
           FROM contact_shared_notes
           WHERE org_contact_id = $1
           ORDER BY created_at DESC""",
        org_contact_id,
    )
    return [dict(r) for r in rows]


@router.post("/shared-notes")
async def create_shared_note(request: Request, body: NoteCreate, username: str = Depends(get_current_user)):
    """Crear nota compartida."""
    db = request.app.state.db_pool
    user = username

    if not body.content.strip():
        raise HTTPException(422, "El contenido no puede estar vacío")

    if not body.contact_id and not body.org_contact_id:
        raise HTTPException(422, "Debe especificar contact_id o org_contact_id")

    row = await db.fetchrow(
        """INSERT INTO contact_shared_notes (contact_id, org_contact_id, author, content, tags)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING *""",
        body.contact_id, body.org_contact_id, user, body.content.strip(), body.tags,
    )
    return dict(row)


@router.put("/shared-notes/{note_id}")
async def update_shared_note(request: Request, note_id: int, body: NoteUpdate, username: str = Depends(get_current_user)):
    """Editar nota — solo el autor puede editar."""
    db = request.app.state.db_pool
    user = username

    row = await db.fetchrow(
        """UPDATE contact_shared_notes
           SET content=$3, tags=$4, updated_at=NOW()
           WHERE id=$1 AND author=$2
           RETURNING *""",
        note_id, user, body.content.strip(), body.tags,
    )
    if not row:
        raise HTTPException(404, "Nota no encontrada o no tiene permisos")
    return dict(row)


@router.delete("/shared-notes/{note_id}")
async def delete_shared_note(request: Request, note_id: int, username: str = Depends(get_current_user)):
    """Eliminar nota — solo el autor."""
    db = request.app.state.db_pool
    user = username

    result = await db.execute(
        "DELETE FROM contact_shared_notes WHERE id=$1 AND author=$2",
        note_id, user,
    )
    if result == "DELETE 0":
        raise HTTPException(404, "Nota no encontrada o no tiene permisos")
    return {"status": "deleted"}
