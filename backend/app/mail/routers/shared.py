"""Shared mailbox access and Send-As delegation for webmail users."""
import asyncio
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password, get_imap_login_user
from app.mail.clients.imap_client import get_imap_connection

router = APIRouter(prefix="/api/mail", tags=["shared-mailboxes"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class DelegationGrant(BaseModel):
    delegate: str = Field(..., min_length=3, max_length=255)
    permissions: list[str] = Field(..., min_length=1)
    """Allowed values: 'read', 'send_as'"""


class DelegationOut(BaseModel):
    id: int
    mailbox: str
    delegate: str
    can_send_as: bool
    created_at: str


class SendAsIdentity(BaseModel):
    email: str
    display_name: str
    type: str  # 'own' or 'delegated'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run_doveadm(cmd_args: list[str]) -> tuple[int, str, str]:
    """Run a doveadm command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "doveadm", *cmd_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
    return proc.returncode, stdout.decode(), stderr.decode()


def _row_to_delegation(row) -> dict:
    d = dict(row)
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    else:
        d["created_at"] = ""
    return d


# ---------------------------------------------------------------------------
# Original shared folders endpoint
# ---------------------------------------------------------------------------

@router.get("/shared/folders")
async def list_shared_folders(request: Request, username: str = Depends(get_current_user)):
    """List folders shared with the current user."""
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        # List all namespaces
        resp = await imap.namespace()

        # List folders including shared namespace
        list_resp = await imap.list('', '*')

        shared_folders = []
        if list_resp.result == "OK":
            for line in list_resp.lines:
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                line = str(line).strip()
                # Look for shared namespace folders (Compartidos/ prefix)
                if "Compartidos/" in line or "shared/" in line.lower():
                    shared_folders.append(line)

        return {"shared_folders": shared_folders}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# BRECHA 5 — Delegation / Send-As endpoints
# ---------------------------------------------------------------------------

@router.get("/delegation/grants")
async def list_delegation_grants(
    request: Request,
    username: str = Depends(get_current_user),
):
    """List mailboxes that have been delegated TO the current user."""
    db = request.app.state.db_pool
    rows = await db.fetch(
        "SELECT * FROM mail_delegation WHERE delegate = $1 ORDER BY created_at",
        username,
    )
    return [_row_to_delegation(r) for r in rows]


@router.post("/delegation/grant", status_code=status.HTTP_201_CREATED)
async def grant_delegation(
    request: Request,
    body: DelegationGrant,
    username: str = Depends(get_current_user),
):
    """Grant delegation from current user's mailbox to another user.
    
    The authenticated user is the OWNER granting access.
    body.delegate is the user who will receive access.
    body.permissions can include 'read' and/or 'send_as'.
    """
    db = request.app.state.db_pool
    delegate = body.delegate.strip().lower()

    # Validate permissions
    valid_perms = {"read", "send_as"}
    for p in body.permissions:
        if p not in valid_perms:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Permiso inválido: {p}. Válidos: {sorted(valid_perms)}",
            )

    # Cannot delegate to yourself
    if delegate == username.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes delegarte a ti mismo",
        )

    # Verify delegate exists in mailbox table
    exists = await db.fetchval(
        "SELECT COUNT(*) FROM mailbox WHERE username = $1 AND active = true",
        delegate,
    )
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Buzón {delegate} no encontrado o inactivo",
        )

    can_send_as = "send_as" in body.permissions
    has_read = "read" in body.permissions

    # Set Dovecot ACL if read permission requested
    if has_read:
        rc, out, err = await _run_doveadm([
            "acl", "set", "-u", username,
            "INBOX", delegate, "lookup", "read", "write", "insert",
        ])
        if rc != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al configurar ACL de Dovecot: {err.strip()}",
            )

    # Upsert into mail_delegation
    row = await db.fetchrow(
        """INSERT INTO mail_delegation (mailbox, delegate, can_send_as)
           VALUES ($1, $2, $3)
           ON CONFLICT (mailbox, delegate)
           DO UPDATE SET can_send_as = $3
           RETURNING *""",
        username, delegate, can_send_as,
    )

    return _row_to_delegation(row)


@router.delete("/delegation/revoke/{delegate_email}")
async def revoke_delegation(
    delegate_email: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Revoke delegation previously granted by the current user."""
    db = request.app.state.db_pool
    delegate = delegate_email.strip().lower()

    # Check it exists
    existing = await db.fetchrow(
        "SELECT * FROM mail_delegation WHERE mailbox = $1 AND delegate = $2",
        username, delegate,
    )
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delegación no encontrada",
        )

    # Remove Dovecot ACL
    rc, out, err = await _run_doveadm([
        "acl", "delete", "-u", username,
        "INBOX", delegate,
    ])
    # We don't fail if doveadm errors — the ACL may already be gone
    if rc != 0:
        # Log but continue
        pass

    # Delete from database
    await db.execute(
        "DELETE FROM mail_delegation WHERE mailbox = $1 AND delegate = $2",
        username, delegate,
    )

    return {"status": "revoked", "delegate": delegate}


@router.get("/delegation/send-as-identities")
async def send_as_identities(
    request: Request,
    username: str = Depends(get_current_user),
):
    """List all identities the user can send as (own + delegated with send_as)."""
    db = request.app.state.db_pool

    # Own identities
    own_rows = await db.fetch(
        "SELECT display_name, email FROM user_identities WHERE username = $1 ORDER BY is_default DESC, created_at",
        username,
    )
    identities: list[dict] = []
    for r in own_rows:
        identities.append({
            "email": r["email"],
            "display_name": r["display_name"],
            "type": "own",
        })

    # If no own identities, add default
    if not identities:
        identities.append({
            "email": username,
            "display_name": username.split("@")[0].replace(".", " ").title(),
            "type": "own",
        })

    # Delegated send-as identities
    delegated_rows = await db.fetch(
        """SELECT d.mailbox, COALESCE(ui.display_name, split_part(d.mailbox, '@', 1)) as display_name
           FROM mail_delegation d
           LEFT JOIN user_identities ui ON ui.username = d.mailbox AND ui.is_default = true
           WHERE d.delegate = $1 AND d.can_send_as = true
           ORDER BY d.created_at""",
        username,
    )
    for r in delegated_rows:
        identities.append({
            "email": r["mailbox"],
            "display_name": r["display_name"],
            "type": "delegated",
        })

    return identities
