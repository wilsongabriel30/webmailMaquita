import json
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/signatures", tags=["signatures"])


def _db(r: Request):
    return r.app.state.db


async def _audit(r, a, action, target=None, details=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""))


async def _ensure_tables(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS mail_signatures (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT DEFAULT '',
            html_content TEXT NOT NULL DEFAULT '',
            text_content TEXT NOT NULL DEFAULT '',
            is_default BOOLEAN DEFAULT false,
            domain VARCHAR(255) DEFAULT '',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            modified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS mail_user_signatures (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) NOT NULL,
            signature_id INT REFERENCES mail_signatures(id) ON DELETE SET NULL,
            custom_html TEXT DEFAULT '',
            custom_name VARCHAR(255) DEFAULT '',
            custom_title VARCHAR(255) DEFAULT '',
            custom_phone VARCHAR(100) DEFAULT '',
            active BOOLEAN DEFAULT true,
            UNIQUE(username)
        );
    """)


# ── Signature Templates ──

@router.get("/templates")
async def list_templates(request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    await _ensure_tables(db)
    rows = await db.fetch("SELECT * FROM mail_signatures ORDER BY name")
    return [dict(r) for r in rows]


@router.post("/templates")
async def create_template(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    db = _db(request)
    await _ensure_tables(db)

    row = await db.fetchrow("""
        INSERT INTO mail_signatures (name, description, html_content, text_content, is_default, domain)
        VALUES ($1, $2, $3, $4, $5, $6) RETURNING *
    """, data.get("name", ""),
        data.get("description", ""),
        data.get("html_content", ""),
        data.get("text_content", ""),
        data.get("is_default", False),
        data.get("domain", ""))

    await _audit(request, admin, "signature_create", data.get("name"))
    return dict(row)


@router.put("/templates/{sig_id}")
async def update_template(sig_id: int, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    db = _db(request)

    row = await db.fetchrow("""
        UPDATE mail_signatures SET name=$2, description=$3, html_content=$4, text_content=$5,
            is_default=$6, domain=$7, modified_at=NOW()
        WHERE id=$1 RETURNING *
    """, sig_id,
        data.get("name", ""), data.get("description", ""),
        data.get("html_content", ""), data.get("text_content", ""),
        data.get("is_default", False), data.get("domain", ""))

    if not row:
        raise HTTPException(404)
    await _audit(request, admin, "signature_update", data.get("name"))
    return dict(row)


@router.delete("/templates/{sig_id}")
async def delete_template(sig_id: int, request: Request, admin: dict = Depends(require_role("superadmin"))):
    db = _db(request)
    await db.execute("DELETE FROM mail_signatures WHERE id = $1", sig_id)
    return {"ok": True}


# ── User Signature Assignments ──

@router.get("/users")
async def list_user_signatures(
    request: Request,
    domain: str = Query(""),
    admin: dict = Depends(get_current_admin),
):
    db = _db(request)
    await _ensure_tables(db)

    if domain:
        rows = await db.fetch("""
            SELECT us.*, s.name as template_name, m.name as user_fullname
            FROM mail_user_signatures us
            LEFT JOIN mail_signatures s ON us.signature_id = s.id
            LEFT JOIN mailbox m ON us.username = m.username
            WHERE us.username LIKE $1
            ORDER BY us.username
        """, f"%@{domain}")
    else:
        rows = await db.fetch("""
            SELECT us.*, s.name as template_name, m.name as user_fullname
            FROM mail_user_signatures us
            LEFT JOIN mail_signatures s ON us.signature_id = s.id
            LEFT JOIN mailbox m ON us.username = m.username
            ORDER BY us.username
        """)
    return [dict(r) for r in rows]


@router.post("/users")
async def assign_signature(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    username = data.get("username", "")
    signature_id = data.get("signature_id")

    if not username:
        raise HTTPException(400, "username requerido")

    db = _db(request)
    await _ensure_tables(db)

    try:
        row = await db.fetchrow("""
            INSERT INTO mail_user_signatures (username, signature_id, custom_name, custom_title, custom_phone)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (username) DO UPDATE SET
                signature_id = $2, custom_name = $3, custom_title = $4, custom_phone = $5
            RETURNING *
        """, username, signature_id,
            data.get("custom_name", ""),
            data.get("custom_title", ""),
            data.get("custom_phone", ""))
    except Exception as e:
        raise HTTPException(400, str(e))

    await _audit(request, admin, "signature_assign", username, {"template_id": signature_id})
    return dict(row)


@router.post("/users/bulk")
async def bulk_assign(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Asignar una firma a multiples usuarios."""
    data = await request.json()
    usernames = data.get("usernames", [])
    signature_id = data.get("signature_id")

    if not usernames or not signature_id:
        raise HTTPException(400, "usernames y signature_id requeridos")

    db = _db(request)
    await _ensure_tables(db)
    assigned = 0
    for u in usernames:
        try:
            await db.execute("""
                INSERT INTO mail_user_signatures (username, signature_id)
                VALUES ($1, $2)
                ON CONFLICT (username) DO UPDATE SET signature_id = $2
            """, u, signature_id)
            assigned += 1
        except Exception:
            pass

    await _audit(request, admin, "signature_bulk_assign", None, {"count": assigned, "template_id": signature_id})
    return {"assigned": assigned}


@router.get("/preview/{sig_id}")
async def preview_signature(sig_id: int, username: str = "", request: Request = None, admin: dict = Depends(get_current_admin)):
    """Preview de firma con datos de usuario sustituidos."""
    db = _db(request)
    sig = await db.fetchrow("SELECT * FROM mail_signatures WHERE id = $1", sig_id)
    if not sig:
        raise HTTPException(404)

    html = sig["html_content"]
    if username:
        user = await db.fetchrow("SELECT * FROM mailbox WHERE username = $1", username)
        user_sig = await db.fetchrow("SELECT * FROM mail_user_signatures WHERE username = $1", username)
        if user:
            html = html.replace("{{nombre}}", user_sig["custom_name"] if user_sig and user_sig["custom_name"] else user["name"])
            html = html.replace("{{email}}", username)
            html = html.replace("{{cargo}}", user_sig["custom_title"] if user_sig else "")
            html = html.replace("{{telefono}}", user_sig["custom_phone"] if user_sig else "")
            html = html.replace("{{dominio}}", user["domain"])

    return {"html": html, "name": sig["name"]}
