import json
from fastapi import APIRouter, Request, HTTPException, Depends
from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/forwarding", tags=["forwarding"])

def _db(r: Request): return r.app.state.db
async def _audit(r, a, action, target=None, details=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""))


@router.get("")
async def list_forwards(request: Request, domain: str = None, admin: dict = Depends(get_current_admin)):
    """Listar todos los reenvios configurados."""
    db = _db(request)
    if domain:
        rows = await db.fetch("""
            SELECT a.address, a.goto, a.domain, a.active, a.created, a.modified,
                   CASE WHEN m.username IS NOT NULL THEN true ELSE false END as has_mailbox
            FROM alias a LEFT JOIN mailbox m ON a.address = m.username
            WHERE a.domain = $1 AND a.address != a.goto AND a.goto != a.address
            ORDER BY a.address
        """, domain)
    else:
        rows = await db.fetch("""
            SELECT a.address, a.goto, a.domain, a.active, a.created, a.modified,
                   CASE WHEN m.username IS NOT NULL THEN true ELSE false END as has_mailbox
            FROM alias a LEFT JOIN mailbox m ON a.address = m.username
            WHERE a.address != a.goto
            ORDER BY a.domain, a.address
        """)
    return [dict(r) for r in rows]


@router.get("/{username:path}")
async def get_forwards_for_user(username: str, request: Request, admin: dict = Depends(get_current_admin)):
    """Ver reenvios de un usuario especifico."""
    db = _db(request)
    rows = await db.fetch(
        "SELECT address, goto, active, created, modified FROM alias WHERE address=$1", username)
    return [dict(r) for r in rows]


@router.post("")
async def create_forward(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Crear reenvio. Puede ser address->goto (simple forward) o address->address,goto (copia + forward)."""
    data = await request.json()
    address = data.get("address", "").strip().lower()
    goto = data.get("goto", "").strip().lower()
    keep_copy = data.get("keep_copy", True)

    if not address or not goto:
        raise HTTPException(400, "address y goto requeridos")

    db = _db(request)
    domain = address.split("@")[1] if "@" in address else ""

    # Si keep_copy, el goto incluye el address original
    final_goto = f"{address},{goto}" if keep_copy else goto

    # Check if alias already exists
    existing = await db.fetchrow("SELECT * FROM alias WHERE address=$1 AND address != goto", address)
    if existing:
        # Update existing
        await db.execute("UPDATE alias SET goto=$2, modified=NOW() WHERE address=$1 AND address != goto", address, final_goto)
    else:
        await db.execute(
            "INSERT INTO alias (address, goto, domain, active) VALUES ($1,$2,$3,true)",
            address, final_goto, domain)

    await _audit(request, admin, "forward_create", address, {"goto": goto, "keep_copy": keep_copy})
    return {"ok": True, "address": address, "goto": final_goto}


@router.delete("/{address:path}")
async def delete_forward(address: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    db = _db(request)
    # Only delete the forward alias, keep self-alias
    r = await db.execute("DELETE FROM alias WHERE address=$1 AND address != goto", address)
    await _audit(request, admin, "forward_delete", address)
    return {"ok": True}
