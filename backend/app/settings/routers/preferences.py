"""User settings router — signature, display name, preferences."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])


class UserSettings(BaseModel):
    display_name: str = ""
    signature_html: str = ""
    messages_per_page: int = 50
    reading_pane: str = "right"
    block_remote_images: bool = True
    confirm_delete: bool = True
    auto_reply_enabled: bool = False
    auto_reply_subject: str = ""
    auto_reply_body: str = ""


class SignatureCreate(BaseModel):
    name: str = "Principal"
    html_content: str = ""
    is_default: bool = False


class SignatureUpdate(BaseModel):
    name: Optional[str] = None
    html_content: Optional[str] = None
    is_default: Optional[bool] = None


def _sig_to_dict(row) -> dict:
    d = dict(row)
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    return d


async def _audit_signature(
    db,
    username: str,
    action: str,
    sig_id: int = None,
    sig_name: str = "",
    old_html: str = "",
    new_html: str = "",
    ip_address: str = "",
    user_agent: str = "",
):
    """Log signature changes for audit/fraud detection."""
    try:
        await db.execute(
            """INSERT INTO signature_audit_log
                (username, action, signature_id, signature_name, old_html, new_html, ip_address, user_agent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            username,
            action,
            sig_id,
            sig_name,
            old_html,
            new_html,
            ip_address,
            user_agent,
        )
    except Exception:
        pass  # Don't let audit failure break the operation


@router.get("")
async def get_settings(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    row = await db.fetchrow(
        "SELECT * FROM user_preferences WHERE username = $1", username
    )
    if row:
        result = dict(row)
        # Fallback: if display_name is empty, use email local part
        if not result.get("display_name"):
            result["display_name"] = username.split("@")[0].replace(".", " ").title()
        return result
    # Return defaults
    return UserSettings(
        display_name=username.split("@")[0].replace(".", " ").title()
    ).model_dump()


@router.put("")
async def update_settings(
    body: UserSettings, request: Request, username: str = Depends(get_current_user)
):
    db = request.app.state.db_pool
    await db.execute(
        """
        INSERT INTO user_preferences (username, display_name, signature_html, messages_per_page,
            reading_pane, block_remote_images, confirm_delete,
            auto_reply_enabled, auto_reply_subject, auto_reply_body, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, now())
        ON CONFLICT (username) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            signature_html = EXCLUDED.signature_html,
            messages_per_page = EXCLUDED.messages_per_page,
            reading_pane = EXCLUDED.reading_pane,
            block_remote_images = EXCLUDED.block_remote_images,
            confirm_delete = EXCLUDED.confirm_delete,
            auto_reply_enabled = EXCLUDED.auto_reply_enabled,
            auto_reply_subject = EXCLUDED.auto_reply_subject,
            auto_reply_body = EXCLUDED.auto_reply_body,
            updated_at = now()
    """,
        username,
        body.display_name,
        body.signature_html,
        body.messages_per_page,
        body.reading_pane,
        body.block_remote_images,
        body.confirm_delete,
        body.auto_reply_enabled,
        body.auto_reply_subject,
        body.auto_reply_body,
    )
    return {"status": "saved"}


@router.get("/signature")
async def get_signature(request: Request, username: str = Depends(get_current_user)):
    """Get default signature - used by compose panel on init."""
    db = request.app.state.db_pool
    # First check user_signatures table for default
    sig_row = await db.fetchrow(
        "SELECT * FROM user_signatures WHERE owner = $1 AND is_default = true LIMIT 1",
        username,
    )
    if sig_row:
        # Get real display_name from preferences
        pref_row = await db.fetchrow(
            "SELECT display_name FROM user_preferences WHERE username = $1", username
        )
        dn = (
            pref_row["display_name"]
            if pref_row and pref_row["display_name"]
            else username.split("@")[0].replace(".", " ").title()
        )
        sig_html = sig_row["html_content"]
        # Clean any unreplaced template variables
        import re as _re

        sig_html = _re.sub(r"\{\{[A-Z0-9_]+\}\}", "", sig_html)
        return {"display_name": dn, "signature_html": sig_html}
    # Fallback to legacy user_preferences
    row = await db.fetchrow(
        "SELECT display_name, signature_html FROM user_preferences WHERE username = $1",
        username,
    )
    if row:
        sig_html = row["signature_html"] or ""
        import re as _re

        sig_html = _re.sub(r"\{\{[A-Z0-9_]+\}\}", "", sig_html)
        return {"display_name": row["display_name"], "signature_html": sig_html}
    return {"display_name": username.split("@")[0], "signature_html": ""}


# -- Multiple Signatures CRUD --


async def _migrate_legacy_signature(db, username: str):
    """If user has no entries in user_signatures, create one from domain template or legacy."""
    count = await db.fetchval(
        "SELECT COUNT(*) FROM user_signatures WHERE owner = $1", username
    )
    if count > 0:
        return
    # Check legacy preferences first
    row = await db.fetchrow(
        "SELECT signature_html FROM user_preferences WHERE username = $1", username
    )
    legacy_html = row["signature_html"] if row and row["signature_html"] else ""
    # If no legacy, try domain template
    if not legacy_html:
        domain = username.split("@")[1] if "@" in username else ""
        if domain:
            tpl_row = await db.fetchrow(
                "SELECT name, html_template FROM default_signatures WHERE domain = $1 OR $1 LIKE domain_pattern",
                domain,
            )
            if tpl_row and tpl_row["html_template"]:
                # Replace placeholders with user info
                local_part = username.split("@")[0]
                display = local_part.replace(".", " ").title()
                html = tpl_row["html_template"]
                html = html.replace("{{NOMBRE}}", display)
                html = html.replace("{{CARGO}}", "")
                html = html.replace("{{EMAIL}}", username)
                html = html.replace("{{TELEFONO1}}", "")
                html = html.replace("{{TELEFONO2}}", "")
                html = html.replace("{{CIUDAD}}", "Quito - Ecuador")
                legacy_html = html
                sig_name = tpl_row["name"] or "Principal"
                await db.execute(
                    "INSERT INTO user_signatures (owner, name, html_content, is_default) VALUES ($1, $2, $3, true)",
                    username,
                    sig_name,
                    legacy_html,
                )
                return
    # Create default entry
    await db.execute(
        "INSERT INTO user_signatures (owner, name, html_content, is_default) VALUES ($1, $2, $3, true)",
        username,
        "Principal",
        legacy_html,
    )


async def _ensure_one_default(db, username: str, exclude_id: int = 0):
    """Ensure there is exactly one default signature."""
    has = await db.fetchval(
        "SELECT COUNT(*) FROM user_signatures WHERE owner = $1 AND is_default = true AND id != $2",
        username,
        exclude_id,
    )
    if has == 0:
        oldest = await db.fetchval(
            "SELECT id FROM user_signatures WHERE owner = $1 AND id != $2 ORDER BY created_at LIMIT 1",
            username,
            exclude_id,
        )
        if oldest:
            await db.execute(
                "UPDATE user_signatures SET is_default = true WHERE id = $1", oldest
            )


@router.get("/signatures")
async def list_signatures(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    await _migrate_legacy_signature(db, username)
    rows = await db.fetch(
        "SELECT * FROM user_signatures WHERE owner = $1 ORDER BY is_default DESC, created_at",
        username,
    )
    return [_sig_to_dict(r) for r in rows]


@router.post("/signatures", status_code=201)
async def create_signature(
    body: SignatureCreate, request: Request, username: str = Depends(get_current_user)
):
    db = request.app.state.db_pool
    count = await db.fetchval(
        "SELECT COUNT(*) FROM user_signatures WHERE owner = $1", username
    )
    if count >= 20:
        raise HTTPException(status_code=400, detail="Maximo 20 firmas")
    if body.is_default:
        await db.execute(
            "UPDATE user_signatures SET is_default = false WHERE owner = $1", username
        )
    row = await db.fetchrow(
        "INSERT INTO user_signatures (owner, name, html_content, is_default) VALUES ($1, $2, $3, $4) RETURNING *",
        username,
        body.name,
        body.html_content,
        body.is_default,
    )
    await _ensure_one_default(db, username)
    await _audit_signature(
        db,
        username,
        "create",
        sig_id=row["id"],
        sig_name=body.name,
        new_html=body.html_content,
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return _sig_to_dict(row)


@router.put("/signatures/{sig_id}")
async def update_signature(
    sig_id: int,
    body: SignatureUpdate,
    request: Request,
    username: str = Depends(get_current_user),
):
    db = request.app.state.db_pool
    existing = await db.fetchrow(
        "SELECT * FROM user_signatures WHERE id = $1 AND owner = $2", sig_id, username
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Firma no encontrada")

    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.html_content is not None:
        updates["html_content"] = body.html_content
    if body.is_default is True:
        await db.execute(
            "UPDATE user_signatures SET is_default = false WHERE owner = $1", username
        )
        updates["is_default"] = True

    if updates:
        set_parts = [f"{k}=${i+2}" for i, k in enumerate(updates.keys())]
        query = (
            f"UPDATE user_signatures SET {', '.join(set_parts)} WHERE id=$1 RETURNING *"
        )
        params = [sig_id] + list(updates.values())
        row = await db.fetchrow(query, *params)
    else:
        row = existing

    await _ensure_one_default(db, username)
    await _audit_signature(
        db,
        username,
        "update",
        sig_id=sig_id,
        sig_name=body.name or existing["name"],
        old_html=existing["html_content"],
        new_html=body.html_content or existing["html_content"],
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return _sig_to_dict(row)


@router.delete("/signatures/{sig_id}")
async def delete_signature(
    sig_id: int, request: Request, username: str = Depends(get_current_user)
):
    db = request.app.state.db_pool
    existing = await db.fetchrow(
        "SELECT * FROM user_signatures WHERE id = $1 AND owner = $2", sig_id, username
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Firma no encontrada")
    count = await db.fetchval(
        "SELECT COUNT(*) FROM user_signatures WHERE owner = $1", username
    )
    if count <= 1:
        raise HTTPException(status_code=400, detail="No puedes eliminar la unica firma")
    await _audit_signature(
        db,
        username,
        "delete",
        sig_id=sig_id,
        sig_name=existing["name"],
        old_html=existing["html_content"],
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    await db.execute("DELETE FROM user_signatures WHERE id = $1", sig_id)
    await _ensure_one_default(db, username, exclude_id=sig_id)
    return {"status": "deleted"}


@router.get("/signatures/load-default")
async def load_default_signature(
    request: Request, username: str = Depends(get_current_user)
):
    """Return domain default signature template for the user to customize."""
    db = request.app.state.db_pool
    domain = username.split("@")[1] if "@" in username else ""
    if not domain:
        return {"template": "", "name": ""}
    tpl_row = await db.fetchrow(
        "SELECT name, html_template FROM default_signatures WHERE domain = $1 OR $1 LIKE domain_pattern",
        domain,
    )
    if not tpl_row or not tpl_row["html_template"]:
        return {"template": "", "name": ""}
    # Return both raw template (with placeholders) and pre-filled version
    raw = tpl_row["html_template"]
    local_part = username.split("@")[0]
    display = local_part.replace(".", " ").title()
    filled = raw.replace("{{NOMBRE}}", display)
    filled = filled.replace("{{CARGO}}", "")
    filled = filled.replace("{{TELEFONO1}}", "")
    filled = filled.replace("{{TELEFONO2}}", "")
    filled = filled.replace("{{EMAIL}}", username)
    filled = filled.replace("{{CIUDAD}}", "Quito - Ecuador")
    return {
        "template": filled,
        "raw_template": raw,
        "name": tpl_row["name"],
        "email": username,
    }
