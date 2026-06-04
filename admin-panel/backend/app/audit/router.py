from fastapi import APIRouter, Request, Depends, Query
from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/audit", tags=["audit"])

def _db(r: Request): return r.app.state.db

@router.get("")
async def get_audit(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    admin_user: str = None,
    action: str = None,
    admin: dict = Depends(get_current_admin),
):
    db = _db(request)
    offset = (page - 1) * per_page
    conditions = []
    params = []
    idx = 1

    if admin_user:
        conditions.append(f"admin_username = ${idx}")
        params.append(admin_user)
        idx += 1
    if action:
        conditions.append(f"action LIKE ${idx}")
        params.append(f"%{action}%")
        idx += 1

    where = f"WHERE { AND .join(conditions)}" if conditions else ""
    total = await db.fetchval(f"SELECT count(*) FROM admin_audit {where}", *params)
    rows = await db.fetch(
        f"SELECT * FROM admin_audit {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}",
        *params, per_page, offset)

    return {"total": total, "page": page, "per_page": per_page, "entries": [dict(r) for r in rows]}
