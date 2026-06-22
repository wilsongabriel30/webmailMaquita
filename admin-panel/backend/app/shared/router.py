"""Shared mailbox management — ACL-based delegation."""
from fastapi import APIRouter, Request, Depends, HTTPException
from app.auth.dependencies import require_role
import subprocess, json, asyncio

router = APIRouter(prefix="/api/shared", tags=["shared-mailboxes"])

async def _audit(request, admin, action, detail=""):
    db = request.app.state.db
    await db.execute(
        "INSERT INTO admin_audit_log(admin_id, username, action, detail, ip) VALUES($1,$2,$3,$4,$5)",
        admin["id"], admin["username"], action, detail,
        request.headers.get("x-real-ip", "unknown")
    )

def _doveadm_acl_get(username: str, folder: str = "INBOX") -> list:
    """Get ACL entries for a user's folder."""
    result = subprocess.run(
        ["doveadm", "acl", "get", "-u", username, folder],
        capture_output=True, text=True, timeout=10
    )
    entries = []
    if result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    entries.append({"id": parts[0], "rights": parts[1:]})
    return entries

def _doveadm_acl_set(username: str, folder: str, target_id: str, rights: list):
    """Set ACL for a folder."""
    cmd = ["doveadm", "acl", "set", "-u", username, folder, target_id] + rights
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise HTTPException(500, f"Error configurando ACL: {result.stderr}")

def _doveadm_acl_delete(username: str, folder: str, target_id: str):
    """Remove ACL entry."""
    cmd = ["doveadm", "acl", "delete", "-u", username, folder, target_id]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise HTTPException(500, f"Error eliminando ACL: {result.stderr}")

@router.get("/mailbox/{username:path}/permissions")
async def get_permissions(username: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Get all shared permissions for a mailbox."""
    folders = ["INBOX", "Sent", "Drafts", "Trash", "Junk"]
    permissions = {}
    for folder in folders:
        try:
            acls = await asyncio.to_thread(_doveadm_acl_get, username, folder)
            if acls:
                permissions[folder] = acls
        except Exception:
            pass
    return {"username": username, "permissions": permissions}

@router.post("/mailbox/{username:path}/grant")
async def grant_access(username: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Grant another user access to this mailbox."""
    body = await request.json()
    delegate = body.get("delegate", "").strip().lower()
    level = body.get("level", "read")
    folders = body.get("folders", ["INBOX"])

    if not delegate or "@" not in delegate:
        raise HTTPException(400, "Se requiere email del delegado")

    rights_map = {
        "read": ["lookup", "read"],
        "write": ["lookup", "read", "write", "write-seen", "write-deleted", "insert"],
        "full": ["lookup", "read", "write", "write-seen", "write-deleted", "insert", "expunge", "create", "delete"],
        "send-as": ["lookup", "read"],
    }

    rights = rights_map.get(level, rights_map["read"])
    target_id = f"user={delegate}"

    for folder in folders:
        await asyncio.to_thread(_doveadm_acl_set, username, folder, target_id, rights)

    await _audit(request, admin, "shared_grant",
                 f"{delegate} -> {username} level={level} folders={','.join(folders)}")

    return {"status": "ok", "message": f"Acceso {level} otorgado a {delegate} en {', '.join(folders)}"}

@router.post("/mailbox/{username:path}/revoke")
async def revoke_access(username: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Revoke a user's access to this mailbox."""
    body = await request.json()
    delegate = body.get("delegate", "").strip().lower()
    folders = body.get("folders", ["INBOX", "Sent", "Drafts", "Trash", "Junk"])

    if not delegate:
        raise HTTPException(400, "Se requiere email del delegado")

    target_id = f"user={delegate}"
    for folder in folders:
        try:
            await asyncio.to_thread(_doveadm_acl_delete, username, folder, target_id)
        except Exception:
            pass

    await _audit(request, admin, "shared_revoke",
                 f"Revoked {delegate} from {username}")

    return {"status": "ok", "message": f"Acceso revocado para {delegate}"}

@router.get("/delegates")
async def list_all_delegations(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """List all shared mailbox delegations across the system."""
    db = request.app.state.db
    rows = await db.fetch("SELECT username FROM mailbox WHERE active = true ORDER BY username")

    delegations = []
    for row in rows:
        username = row["username"]
        try:
            acls = await asyncio.to_thread(_doveadm_acl_get, username, "INBOX")
            for acl in acls:
                if acl["id"].startswith("user="):
                    delegate = acl["id"].replace("user=", "")
                    delegations.append({
                        "mailbox": username,
                        "delegate": delegate,
                        "rights": acl["rights"],
                        "folder": "INBOX"
                    })
        except Exception:
            pass

    return {"delegations": delegations}
