import json
from fastapi import APIRouter, Request, HTTPException, Depends
from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/aliases", tags=["aliases"])

def _db(r: Request): return r.app.state.db

async def _audit(r, a, action, target=None, details=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""))

@router.get("")
async def list_aliases(request: Request, domain: str = None, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    if domain:
        rows = await db.fetch("SELECT address, goto, domain, active, created, modified FROM alias WHERE domain=$1 AND address!=goto ORDER BY address", domain)
    else:
        rows = await db.fetch("SELECT address, goto, domain, active, created, modified FROM alias WHERE address!=goto ORDER BY domain, address")
    return [dict(r) for r in rows]

@router.post("", status_code=201)
async def create_alias(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    address = data.get("address", "").strip().lower()
    goto = data.get("goto", "").strip().lower()
    if not address or not goto:
        raise HTTPException(400, "address y goto requeridos")
    domain = address.split("@")[1] if "@" in address else ""
    try:
        row = await _db(request).fetchrow(
            "INSERT INTO alias (address,goto,domain,active) VALUES ($1,$2,$3,$4) RETURNING address,goto,domain,active,created,modified",
            address, goto, domain, data.get("active", True))
    except Exception as e:
        raise HTTPException(400, str(e))
    await _audit(request, admin, "alias_create", address, {"goto": goto})
    return dict(row)

@router.put("/{address:path}")
async def update_alias(address: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    db = _db(request)
    cur = await db.fetchrow("SELECT * FROM alias WHERE address=$1", address)
    if not cur: raise HTTPException(404)
    row = await db.fetchrow(
        "UPDATE alias SET goto=$2, active=$3, modified=NOW() WHERE address=$1 RETURNING address,goto,domain,active,created,modified",
        address, data.get("goto", cur["goto"]), data.get("active", cur["active"]))
    await _audit(request, admin, "alias_update", address, data)
    return dict(row)

@router.delete("/{address:path}")
async def delete_alias(address: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    r = await _db(request).execute("DELETE FROM alias WHERE address=$1", address)
    if r != "DELETE 1": raise HTTPException(404)
    await _audit(request, admin, "alias_delete", address)
    return {"ok": True}
