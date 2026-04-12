"""Data Retention Policies — Maquita Webmail."""
import asyncio
import subprocess
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from app.auth.dependencies import require_admin

logger = logging.getLogger("retention")

router = APIRouter(prefix="/api/admin/retention", tags=["retention"])


def _get_db(request: Request):
    return request.app.state.db_pool


# ---------- CRUD ----------

@router.get("")
async def list_policies(request: Request, admin: str = Depends(require_admin)):
    """Listar todas las politicas de retencion."""
    db = _get_db(request)
    rows = await db.fetch("SELECT * FROM retention_policies ORDER BY id")
    return [dict(r) for r in rows]


@router.post("", status_code=201)
async def create_policy(request: Request, admin: str = Depends(require_admin)):
    """Crear nueva politica de retencion."""
    data = await request.json()
    required = ["name", "target", "max_age_days"]
    for field in required:
        if field not in data or not data[field]:
            raise HTTPException(400, f"Campo requerido: {field}")

    db = _get_db(request)
    row = await db.fetchrow(
        """INSERT INTO retention_policies
           (name, description, target, folder_pattern, max_age_days, action, move_to, is_active)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *""",
        data["name"],
        data.get("description", ""),
        data["target"],
        data.get("folder_pattern", "*"),
        int(data["max_age_days"]),
        data.get("action", "delete"),
        data.get("move_to"),
        data.get("is_active", True),
    )
    return dict(row)


@router.put("/{policy_id}")
async def update_policy(policy_id: int, request: Request, admin: str = Depends(require_admin)):
    """Editar politica de retencion."""
    data = await request.json()
    db = _get_db(request)

    existing = await db.fetchrow("SELECT id FROM retention_policies WHERE id = $1", policy_id)
    if not existing:
        raise HTTPException(404, "Politica no encontrada")

    fields = []
    values = []
    idx = 1
    for key in ["name", "description", "target", "folder_pattern", "max_age_days", "action", "move_to", "is_active"]:
        if key in data:
            fields.append(f"{key} = ${idx}")
            val = data[key]
            if key == "max_age_days":
                val = int(val)
            values.append(val)
            idx += 1

    if not fields:
        raise HTTPException(400, "No hay campos para actualizar")

    values.append(policy_id)
    query = f"UPDATE retention_policies SET {', '.join(fields)} WHERE id = ${idx} RETURNING *"
    row = await db.fetchrow(query, *values)
    return dict(row)


@router.delete("/{policy_id}")
async def delete_policy(policy_id: int, request: Request, admin: str = Depends(require_admin)):
    """Eliminar politica de retencion."""
    db = _get_db(request)
    result = await db.execute("DELETE FROM retention_policies WHERE id = $1", policy_id)
    if result == "DELETE 0":
        raise HTTPException(404, "Politica no encontrada")
    return {"ok": True}


# ---------- Ejecucion ----------

def _get_target_users(target: str):
    """Resolve target to user list. Returns None for 'all' (use -A flag)."""
    if target == "all":
        return None
    if target.startswith("domain:"):
        domain = target.split(":", 1)[1]
        result = subprocess.run(
            ["doveadm", "user", f"*@{domain}"],
            capture_output=True, text=True, timeout=30
        )
        return [u.strip() for u in result.stdout.strip().split("\n") if u.strip()]
    if target.startswith("user:"):
        return [target.split(":", 1)[1]]
    return None


def _count_messages(user_flag, folder, days):
    """Count messages matching criteria using doveadm search."""
    try:
        cmd = ["doveadm", "search"] + user_flag + ["mailbox", folder, "savedbefore", f"{days}d"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return 0
        lines = result.stdout.strip().split("\n")
        return len(lines) if lines[0] else 0
    except Exception:
        return 0


def _expunge_messages(user_flag, folder, days):
    """Expunge messages matching criteria using doveadm expunge."""
    try:
        cmd = ["doveadm", "expunge"] + user_flag + ["mailbox", folder, "savedbefore", f"{days}d"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    except Exception:
        return False


@router.get("/{policy_id}/preview")
async def preview_policy(policy_id: int, request: Request, admin: str = Depends(require_admin)):
    """Preview: cuantos mensajes serian afectados."""
    db = _get_db(request)
    policy = await db.fetchrow("SELECT * FROM retention_policies WHERE id = $1", policy_id)
    if not policy:
        raise HTTPException(404, "Politica no encontrada")

    def _do_preview():
        users = _get_target_users(policy["target"])
        folder = policy["folder_pattern"]
        days = policy["max_age_days"]
        total = 0

        if users is None:
            total = _count_messages(["-A"], folder, days)
        else:
            for user in users:
                total += _count_messages(["-u", user], folder, days)

        return total

    loop = asyncio.get_event_loop()
    count = await loop.run_in_executor(None, _do_preview)

    return {"policy_id": policy_id, "name": policy["name"], "messages_affected": count}


@router.post("/{policy_id}/run")
async def run_policy(
    policy_id: int,
    request: Request,
    dry_run: bool = Query(True, description="Solo simular, no ejecutar"),
    admin: str = Depends(require_admin),
):
    """Ejecutar politica manualmente. dry_run=true por defecto."""
    db = _get_db(request)
    policy = await db.fetchrow("SELECT * FROM retention_policies WHERE id = $1", policy_id)
    if not policy:
        raise HTTPException(404, "Politica no encontrada")

    def _do_run():
        users = _get_target_users(policy["target"])
        folder = policy["folder_pattern"]
        days = policy["max_age_days"]
        action = policy["action"]

        if users is None:
            user_flag = ["-A"]
            count = _count_messages(user_flag, folder, days)
            if not dry_run and action == "delete":
                _expunge_messages(user_flag, folder, days)
            return count
        else:
            total = 0
            for user in users:
                uf = ["-u", user]
                c = _count_messages(uf, folder, days)
                total += c
                if not dry_run and action == "delete":
                    _expunge_messages(uf, folder, days)
            return total

    loop = asyncio.get_event_loop()
    count = await loop.run_in_executor(None, _do_run)

    if not dry_run:
        await db.execute(
            "UPDATE retention_policies SET last_run = NOW(), messages_affected = $1 WHERE id = $2",
            count, policy_id
        )
        logger.info(f"Retention policy {policy_id} ejecutada: {count} mensajes afectados")

    return {
        "policy_id": policy_id,
        "name": policy["name"],
        "dry_run": dry_run,
        "messages_affected": count,
        "action": policy["action"],
    }
