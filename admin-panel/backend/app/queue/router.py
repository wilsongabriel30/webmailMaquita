import json
from fastapi import APIRouter, Request, HTTPException, Depends
from app.auth.dependencies import get_current_admin, require_role
from app.wrappers import postfix

router = APIRouter(prefix="/api/queue", tags=["queue"])

def _db(r: Request): return r.app.state.db
async def _audit(r, a, action, target=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) VALUES ($1,$2,$3,$4,$5)",
        a["id"], a["username"], action, target, r.headers.get("X-Real-IP", r.client.host if r.client else ""))

@router.get("")
async def get_queue(admin: dict = Depends(get_current_admin)):
    return await postfix.list_queue()

@router.post("/action")
async def queue_action(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    action = data.get("action", "")
    qid = data.get("queue_id")
    # Map actions to functions
    if action == "flush":
        fn = postfix.flush_all if not qid or qid == "ALL" else lambda: postfix.flush_one(qid)
    elif action == "flush_all":
        fn = postfix.flush_all
    elif action == "delete":
        fn = postfix.delete_all if not qid or qid == "ALL" else lambda: postfix.delete_one(qid)
    elif action == "delete_all":
        fn = postfix.delete_all
    elif action == "hold":
        if not qid or qid == "ALL":
            raise HTTPException(400, "Se requiere un queue_id especifico para hold")
        fn = lambda: postfix.hold_one(qid)
    elif action == "release":
        if not qid or qid == "ALL":
            raise HTTPException(400, "Se requiere un queue_id especifico para release")
        fn = lambda: postfix.release_one(qid)
    elif action == "requeue":
        fn = postfix.requeue_all if not qid or qid == "ALL" else lambda: postfix.requeue_one(qid)
    elif action == "requeue_all":
        fn = postfix.requeue_all
    else:
        raise HTTPException(400, f"Accion invalida: {action}")
    try:
        await fn()
    except Exception as e:
        raise HTTPException(500, f"Error ejecutando {action}: {str(e)}")
    await _audit(request, admin, f"queue_{action}", qid)
    return {"ok": True}
