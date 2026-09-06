"""API Keys management router + authentication dependency."""

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user

logger = logging.getLogger("apikeys")

router = APIRouter(prefix="/api/keys", tags=["api-keys"])

# ---------- Pydantic models ----------


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    permissions: list[str] = Field(default=["read"])
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)


class ApiKeyOut(BaseModel):
    id: int
    name: str
    prefix: str
    permissions: list[str]
    is_active: bool
    created_at: str
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None


# ---------- Helpers ----------

# _get_user_id removed in Fase 2 cleanup - using user_email directly


def _row_to_dict(row) -> dict:
    d = dict(row)
    for k in ("created_at", "last_used_at", "expires_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
        else:
            d[k] = None
    return d


# ---------- Endpoints ----------


@router.post("", status_code=201)
async def create_api_key(
    body: ApiKeyCreate, request: Request, username: str = Depends(get_current_user)
):
    valid_perms = {"read", "write", "admin"}
    for p in body.permissions:
        if p not in valid_perms:
            raise HTTPException(400, f"Invalid permission: {p}")
    db = request.app.state.db_pool
    raw_token = secrets.token_urlsafe(32)
    full_key = f"mk_{raw_token}"
    prefix = full_key[:11]  # mk_ + 8 chars
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    expires_at = None
    if body.expires_in_days:
        from datetime import timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)
    row = await db.fetchrow(
        """INSERT INTO api_keys (user_email, name, key_hash, prefix, permissions, expires_at)
           VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
        username,
        body.name,
        key_hash,
        prefix,
        body.permissions,
        expires_at,
    )
    result = _row_to_dict(row)
    result["key"] = full_key  # Only returned once!
    return result


@router.get("")
async def list_api_keys(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    rows = await db.fetch(
        "SELECT id, name, prefix, permissions, is_active, created_at, last_used_at, expires_at FROM api_keys WHERE user_email = $1 ORDER BY id",
        username,
    )
    return [_row_to_dict(r) for r in rows]


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: int, request: Request, username: str = Depends(get_current_user)
):
    db = request.app.state.db_pool
    result = await db.execute(
        "DELETE FROM api_keys WHERE id = $1 AND user_email = $2", key_id, username
    )
    if result == "DELETE 0":
        raise HTTPException(404, "API key not found")
    return None


# ---------- Auth dependency for API key support ----------


async def get_current_user_or_apikey(request: Request) -> str:
    """Authenticate via JWT cookie OR X-API-Key header."""
    # Try API key first
    api_key = request.headers.get("X-API-Key")
    if api_key and api_key.startswith("mk_"):
        db = request.app.state.db_pool
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        row = await db.fetchrow(
            """SELECT * FROM api_keys
               WHERE key_hash = $1 AND is_active = true""",
            key_hash,
        )
        if not row:
            raise HTTPException(401, "Invalid API key")
        if row["expires_at"] and row["expires_at"].replace(
            tzinfo=timezone.utc
        ) < datetime.now(timezone.utc):
            raise HTTPException(401, "API key expired")
        # Update last_used_at
        await db.execute(
            "UPDATE api_keys SET last_used_at = NOW() WHERE id = $1", row["id"]
        )
        # Store permissions in request state for downstream use
        request.state.api_key_permissions = list(row["permissions"])
        return row["user_email"]

    # Fall back to JWT
    return await get_current_user(request)
