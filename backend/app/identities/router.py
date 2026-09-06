from app.core.sanitize import sanitize_html

"""Email identities router — multiple From addresses."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/identities", tags=["identities"])


class IdentityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=3, max_length=255)
    signature_html: Optional[str] = ""
    is_default: Optional[bool] = False


class IdentityUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    signature_html: Optional[str] = None
    is_default: Optional[bool] = None


async def _ensure_default(db, username: str, exclude_id: Optional[int] = None):
    """If user has no default identity, promote the oldest one."""
    if exclude_id:
        has = await db.fetchval(
            "SELECT COUNT(*) FROM user_identities WHERE username=$1 AND is_default=true AND id!=$2",
            username, exclude_id)
    else:
        has = await db.fetchval(
            "SELECT COUNT(*) FROM user_identities WHERE username=$1 AND is_default=true", username)
    if has == 0:
        if exclude_id:
            oldest = await db.fetchval(
                "SELECT id FROM user_identities WHERE username=$1 AND id!=$2 ORDER BY created_at LIMIT 1",
                username, exclude_id)
        else:
            oldest = await db.fetchval(
                "SELECT id FROM user_identities WHERE username=$1 ORDER BY created_at LIMIT 1", username)
        if oldest:
            await db.execute("UPDATE user_identities SET is_default=true WHERE id=$1", oldest)


def _row_to_dict(row) -> dict:
    d = dict(row)
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    else:
        d["created_at"] = ""
    return d


@router.get("")
async def list_identities(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    rows = await db.fetch(
        "SELECT * FROM user_identities WHERE username=$1 ORDER BY created_at", username)
    if not rows:
        # Auto-create default identity
        row = await db.fetchrow(
            "INSERT INTO user_identities (username, display_name, email, signature_html, is_default) "
            "VALUES ($1, $2, $3, '', true) RETURNING *",
            username, username.split("@")[0].replace(".", " ").title(), username)
        rows = [row]
    return [_row_to_dict(r) for r in rows]


async def _user_owns_email(db, username: str, email: str) -> bool:
    """Check if user owns the email: is their primary address or an alias pointing to them."""
    email = email.strip().lower()
    # Primary address
    if email == username.lower():
        return True
    # Check aliases in PostfixAdmin alias table
    row = await db.fetchrow(
        "SELECT goto FROM alias WHERE address = $1 AND active = true", email)
    if row and username.lower() in row["goto"].lower():
        return True
    return False


@router.post("", status_code=201)
async def create_identity(request: Request, body: IdentityCreate, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool

    # Validate email belongs to user (primary or alias)
    if not await _user_owns_email(db, username, body.email):
        raise HTTPException(
            status_code=403,
            detail=f"No tienes permiso para usar {body.email} como identidad. Solo puedes usar tu dirección principal o alias asignados.")

    count = await db.fetchval("SELECT COUNT(*) FROM user_identities WHERE username=$1", username)
    if count >= 10:
        raise HTTPException(status_code=400, detail="Maximo 10 identidades")
    if body.is_default:
        await db.execute("UPDATE user_identities SET is_default=false WHERE username=$1", username)
    row = await db.fetchrow(
        "INSERT INTO user_identities (username, display_name, email, signature_html, is_default) "
        "VALUES ($1, $2, $3, $4, $5) RETURNING *",
        username, body.name, body.email, body.signature_html or "", bool(body.is_default))
    await _ensure_default(db, username)
    return _row_to_dict(row)


@router.put("/{identity_id}")
async def update_identity(identity_id: int, request: Request, body: IdentityUpdate, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    existing = await db.fetchrow(
        "SELECT * FROM user_identities WHERE id=$1 AND username=$2", identity_id, username)
    if not existing:
        raise HTTPException(status_code=404, detail="Identidad no encontrada")

    updates = {}
    if body.name is not None:
        updates["display_name"] = body.name
    if body.email is not None:
        if not await _user_owns_email(db, username, body.email):
            raise HTTPException(status_code=403, detail=f"No tienes permiso para usar {body.email} como identidad")
        updates["email"] = body.email
    if body.signature_html is not None:
        updates["signature_html"] = body.signature_html
    if body.is_default is True:
        await db.execute("UPDATE user_identities SET is_default=false WHERE username=$1", username)
        updates["is_default"] = True

    if updates:
        set_parts = [f"{k}=${i+2}" for i, k in enumerate(updates.keys())]
        query = f"UPDATE user_identities SET {', '.join(set_parts)} WHERE id=$1 RETURNING *"
        params = [identity_id] + list(updates.values())
        row = await db.fetchrow(query, *params)
    else:
        row = existing

    await _ensure_default(db, username)
    return _row_to_dict(row)


@router.delete("/{identity_id}")
async def delete_identity(identity_id: int, request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    existing = await db.fetchrow(
        "SELECT * FROM user_identities WHERE id=$1 AND username=$2", identity_id, username)
    if not existing:
        raise HTTPException(status_code=404, detail="Identidad no encontrada")
    count = await db.fetchval("SELECT COUNT(*) FROM user_identities WHERE username=$1", username)
    if count <= 1:
        raise HTTPException(status_code=400, detail="No puedes eliminar la unica identidad")
    await db.execute("DELETE FROM user_identities WHERE id=$1", identity_id)
    await _ensure_default(db, username, exclude_id=identity_id)
    return {"status": "deleted"}
