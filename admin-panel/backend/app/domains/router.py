from fastapi import APIRouter, Request, HTTPException, Depends
from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/domains", tags=["domains"])


def _db(r: Request):
    return r.app.state.db


async def _audit(r: Request, admin: dict, action: str, target: str = None, details: dict = None):
    await r.app.state.db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        admin["id"], admin["username"], action, target,
        __import__("json").dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )


@router.get("")
async def list_domains(request: Request, admin: dict = Depends(get_current_admin)):
    rows = await _db(request).fetch("""
        SELECT d.domain, d.description, d.aliases, d.mailboxes, d.maxquota,
               d.quota, d.active, d.created, d.modified,
               (SELECT count(*) FROM mailbox m WHERE m.domain = d.domain) as mailbox_count,
               (SELECT count(*) FROM alias a WHERE a.domain = d.domain AND a.address != a.goto) as alias_count
        FROM domain d ORDER BY d.domain
    """)
    return [dict(r) for r in rows]


@router.get("/{domain}")
async def get_domain(domain: str, request: Request, admin: dict = Depends(get_current_admin)):
    row = await _db(request).fetchrow("""
        SELECT d.*, 
               (SELECT count(*) FROM mailbox m WHERE m.domain = d.domain) as mailbox_count,
               (SELECT count(*) FROM alias a WHERE a.domain = d.domain AND a.address != a.goto) as alias_count
        FROM domain d WHERE d.domain = $1
    """, domain)
    if not row:
        raise HTTPException(404, "Dominio no encontrado")
    return dict(row)


@router.post("", status_code=201)
async def create_domain(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    name = data.get("domain", "").strip().lower()
    if not name:
        raise HTTPException(400, "Nombre de dominio requerido")
    try:
        row = await _db(request).fetchrow(
            "INSERT INTO domain (domain, description, aliases, mailboxes, maxquota, quota, active) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *",
            name, data.get("description", ""), data.get("aliases", 0), data.get("mailboxes", 0),
            data.get("maxquota", 0), data.get("quota", 0), data.get("active", True),
        )
    except Exception as e:
        raise HTTPException(400, str(e))
    await _audit(request, admin, "domain_create", name)
    return dict(row)


@router.put("/{domain}")
async def update_domain(domain: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    db = _db(request)
    cur = await db.fetchrow("SELECT * FROM domain WHERE domain = $1", domain)
    if not cur:
        raise HTTPException(404)
    row = await db.fetchrow("""
        UPDATE domain SET description=$2, aliases=$3, mailboxes=$4, maxquota=$5, quota=$6, active=$7, modified=NOW()
        WHERE domain=$1 RETURNING *
    """, domain, data.get("description", cur["description"]), data.get("aliases", cur["aliases"]),
        data.get("mailboxes", cur["mailboxes"]), data.get("maxquota", cur["maxquota"]),
        data.get("quota", cur["quota"]), data.get("active", cur["active"]))
    await _audit(request, admin, "domain_update", domain, data)
    return dict(row)


@router.delete("/{domain}")
async def delete_domain(domain: str, request: Request, admin: dict = Depends(require_role("superadmin"))):
    db = _db(request)
    cnt = await db.fetchval("SELECT count(*) FROM mailbox WHERE domain = $1", domain)
    if cnt > 0:
        raise HTTPException(400, f"No se puede eliminar: tiene {cnt} buzon(es)")
    r = await db.execute("DELETE FROM domain WHERE domain = $1", domain)
    if r != "DELETE 1":
        raise HTTPException(404)
    await _audit(request, admin, "domain_delete", domain)
    return {"ok": True}
