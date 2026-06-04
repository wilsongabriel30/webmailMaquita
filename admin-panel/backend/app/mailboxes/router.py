import asyncio
from asyncio.subprocess import PIPE
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from app.auth.dependencies import get_current_admin, require_role
from app.wrappers.doveadm import generate_password_hash, verify_password, get_quota, get_mailbox_status
import json

router = APIRouter(prefix="/api/mailboxes", tags=["mailboxes"])


def _db(r: Request):
    return r.app.state.db


async def _audit(r, a, action, target=None, details=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target,
        json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )


async def _run(*cmd) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    out, err = await proc.communicate()
    return out.decode(errors="replace"), err.decode(errors="replace"), proc.returncode


@router.get("")
async def list_mailboxes(request: Request, domain: str = None, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    if domain:
        rows = await db.fetch(
            "SELECT username, name, domain, quota, active, local_part, phone, email_other, created, modified FROM mailbox WHERE domain=$1 ORDER BY username", domain)
    else:
        rows = await db.fetch(
            "SELECT username, name, domain, quota, active, local_part, phone, email_other, created, modified FROM mailbox ORDER BY domain, username")
    return [dict(r) for r in rows]


@router.get("/search/autocomplete")
async def autocomplete_mailbox(
    q: str = Query("", min_length=1),
    limit: int = Query(10, ge=1, le=50),
    request: Request = None,
    admin: dict = Depends(get_current_admin),
):
    db = _db(request)
    rows = await db.fetch(
        """SELECT username, name, domain, active FROM mailbox
           WHERE username ILIKE $1 OR name ILIKE $1
           ORDER BY username LIMIT $2""",
        f"%{q}%", limit,
    )
    return [dict(r) for r in rows]


@router.get("/{username:path}/detail")
async def get_mailbox_detail(username: str, request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    row = await db.fetchrow("SELECT * FROM mailbox WHERE username = $1", username)
    if not row:
        raise HTTPException(404)
    result = dict(row)
    result.pop("password", None)
    try:
        result["quota_usage"] = await get_quota(username)
    except Exception:
        result["quota_usage"] = None
    try:
        result["folders"] = await get_mailbox_status(username)
    except Exception:
        result["folders"] = []
    return result


@router.post("", status_code=201)
async def create_mailbox(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    if not username or "@" not in username:
        raise HTTPException(400, "Username en formato user@domain requerido")
    if not password or len(password) < 6:
        raise HTTPException(400, "Password minimo 6 caracteres")

    domain = username.split("@")[1]
    local = username.split("@")[0]
    pw_hash = await generate_password_hash(password)
    db = _db(request)

    try:
        row = await db.fetchrow("""
            INSERT INTO mailbox (username, password, name, maildir, quota, domain, local_part, active)
            VALUES ($1::varchar, $2::varchar, $3::varchar, $4::varchar, $5, $6::varchar, $7::varchar, $8)
            RETURNING username, name, domain, quota, active, local_part, created, modified
        """, username, pw_hash, data.get("name", ""), f"{domain}/{local}/",
            data.get("quota", 0), domain, local, data.get("active", True))
    except Exception as e:
        err = str(e)
        if "duplicate key" in err or "already exists" in err:
            raise HTTPException(409, f"El buzon {username} ya existe")
        import logging; logging.getLogger("admin").error("Create mailbox error: %s", err)
        if "foreign key" in err and "domain" in err:
            raise HTTPException(400, f"El dominio {domain} no existe. Creelo primero desde Dominios en el panel de administracion.")
        raise HTTPException(400, f"Error al crear el buzon: {err}")

    await db.execute("INSERT INTO alias (address, goto, domain, active) VALUES ($1::varchar,$1::varchar,$2::varchar,true) ON CONFLICT DO NOTHING", username, domain)
    await _audit(request, admin, "mailbox_create", username)
    return dict(row)


@router.put("/{username:path}")
async def update_mailbox(username: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    db = _db(request)
    cur = await db.fetchrow("SELECT * FROM mailbox WHERE username = $1", username)
    if not cur:
        raise HTTPException(404)

    pw = cur["password"]
    pw_changed = False
    if data.get("password"):
        pw = await generate_password_hash(data["password"])
        pw_changed = True

    row = await db.fetchrow("""
        UPDATE mailbox SET name=$2, password=$3, quota=$4, active=$5, phone=$6, email_other=$7, modified=NOW()
        WHERE username=$1 RETURNING username, name, domain, quota, active, local_part, phone, email_other, created, modified
    """, username,
        data.get("name", cur["name"]), pw,
        data.get("quota", cur["quota"]), data.get("active", cur["active"]),
        data.get("phone", cur["phone"]), data.get("email_other", cur["email_other"]))

    if pw_changed and not await verify_password(username, data["password"]):
        raise HTTPException(500, "La contrasena no se aplico correctamente. Intente nuevamente.")
    await _audit(request, admin, "mailbox_update", username, {k: v for k, v in data.items() if k != "password"})
    return dict(row)


@router.delete("/{username:path}")
async def delete_mailbox(username: str, request: Request, admin: dict = Depends(require_role("superadmin"))):
    db = _db(request)
    await db.execute("DELETE FROM alias WHERE address=$1 AND goto=$1", username)
    await db.execute("DELETE FROM alias WHERE goto LIKE $1", f"%{username}%")
    r = await db.execute("DELETE FROM mailbox WHERE username = $1", username)
    if r != "DELETE 1":
        raise HTTPException(404)
    await _audit(request, admin, "mailbox_delete", username)
    return {"ok": True}


@router.post("/{username:path}/toggle-active")
async def toggle_active(username: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    db = _db(request)
    row = await db.fetchrow("UPDATE mailbox SET active = NOT active, modified=NOW() WHERE username=$1 RETURNING username, active", username)
    if not row:
        raise HTTPException(404)
    await _audit(request, admin, "mailbox_toggle", username, {"active": row["active"]})
    return dict(row)


# ── Cambiar titular de cuenta ──

@router.post("/{username:path}/cambiar-titular")
async def cambiar_titular(
    username: str, request: Request,
    admin: dict = Depends(require_role("superadmin", "admin")),
):
    """
    Cambia el titular de una cuenta de correo:
    1. Actualiza nombre en la base de datos
    2. Cambia contrasena obligatoriamente
    3. Actualiza firma si tiene plantilla asignada
    4. Opcionalmente envia correo de notificacion a contactos recientes
    """
    data = await request.json()
    db = _db(request)

    new_name = data.get("new_name", "").strip()
    new_password = data.get("new_password", "")
    new_cargo = data.get("new_cargo", "").strip()
    new_phone = data.get("new_phone", "").strip()
    send_notification = data.get("send_notification", False)
    notification_message = data.get("notification_message", "")

    if not new_name:
        raise HTTPException(400, "El nombre del nuevo titular es obligatorio")
    if not new_password or len(new_password) < 6:
        raise HTTPException(400, "La contrasena del nuevo titular es obligatoria (minimo 6 caracteres)")

    # 1. Verify mailbox exists
    cur = await db.fetchrow("SELECT * FROM mailbox WHERE username = $1", username)
    if not cur:
        raise HTTPException(404, "Buzon no encontrado")

    old_name = cur["name"]

    # 2. Update name and password
    pw_hash = await generate_password_hash(new_password)
    await db.execute(
        "UPDATE mailbox SET name=$2, password=$3, phone=$4, modified=NOW() WHERE username=$1",
        username, new_name, pw_hash, new_phone or cur["phone"]
    )
    # GARANTIA anti-desincronizacion: confirmar que la nueva contrasena autentica
    if not await verify_password(username, new_password):
        raise HTTPException(500, "La contrasena no se aplico correctamente. Intente nuevamente.")

    # 3. Update signature if has template assigned
    sig_updated = False
    try:
        sig_row = await db.fetchrow(
            "SELECT id FROM mail_user_signatures WHERE username = $1", username
        )
        if sig_row:
            await db.execute(
                "UPDATE mail_user_signatures SET custom_name=$2, custom_title=$3, custom_phone=$4 WHERE username=$1",
                username, new_name, new_cargo, new_phone
            )
            sig_updated = True
    except Exception:
        pass  # Table may not exist yet

    # 4. Send notification email to recent contacts (via sendmail)
    notification_sent = False
    recipients_count = 0
    if send_notification:
        try:
            domain = username.split("@")[1]
            # Get recent recipients from mail log (last 30 days of sent mail)
            # Use doveadm to find unique To: addresses from Sent folder
            out, _, rc = await _run(
                "doveadm", "search", "-u", username, "mailbox", "Sent", "since", "30d"
            )
            # Get unique recipients from sent folder headers
            recipients = set()
            if rc == 0 and out.strip():
                guids_uids = out.strip().split("\n")[:100]  # Limit to 100
                for line in guids_uids:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        try:
                            hdr_out, _, hrc = await _run(
                                "doveadm", "fetch", "-u", username,
                                "hdr.to", f"mailbox-guid {parts[0]} uid {parts[1]}"
                            )
                            if hrc == 0:
                                for hdr_line in hdr_out.split("\n"):
                                    hdr_line = hdr_line.strip()
                                    if "@" in hdr_line and hdr_line != username:
                                        # Extract email from header
                                        import re
                                        emails = re.findall(r'[\w.+-]+@[\w.-]+', hdr_line)
                                        for em in emails:
                                            if em != username and domain not in em:
                                                # Only external contacts
                                                pass
                                            if em != username:
                                                recipients.add(em.lower())
                        except Exception:
                            continue

            # Also get internal users (all mailboxes in same domain)
            internal = await db.fetch(
                "SELECT username FROM mailbox WHERE domain=$1 AND username != $2 AND active=true",
                domain, username
            )
            for r in internal:
                recipients.add(r["username"])

            if recipients:
                # Build notification email
                subject = f"Cambio de titular: {username}"
                body = notification_message or (
                    f"Estimados,\n\n"
                    f"Les informamos que el buzon de correo {username} "
                    f"ha sido asignado a {new_name}"
                    f"{' - ' + new_cargo if new_cargo else ''}.\n\n"
                    f"Titular anterior: {old_name}\n"
                    f"Nuevo titular: {new_name}\n"
                    f"{('Cargo: ' + new_cargo + chr(10)) if new_cargo else ''}"
                    f"{('Telefono: ' + new_phone + chr(10)) if new_phone else ''}"
                    f"\nPor favor actualice sus contactos.\n\n"
                    f"Saludos cordiales,\n"
                    f"Administracion de Correo - Maquita Cushunchic"
                )

                # Send via sendmail to each recipient (batched)
                for recipient in list(recipients)[:200]:  # Limit to 200
                    email_msg = (
                        f"From: {new_name} <{username}>\n"
                        f"To: {recipient}\n"
                        f"Subject: {subject}\n"
                        f"Content-Type: text/plain; charset=utf-8\n"
                        f"X-Mailer: Maquita-Admin-Panel\n"
                        f"\n"
                        f"{body}\n"
                    )
                    proc = await asyncio.create_subprocess_exec(
                        "sendmail", "-t", "-f", username,
                        stdin=PIPE, stdout=PIPE, stderr=PIPE
                    )
                    await proc.communicate(input=email_msg.encode())

                notification_sent = True
                recipients_count = len(recipients)
        except Exception as e:
            notification_sent = False

    await _audit(request, admin, "mailbox_cambiar_titular", username, {
        "old_name": old_name,
        "new_name": new_name,
        "new_cargo": new_cargo,
        "password_changed": True,
        "signature_updated": sig_updated,
        "notification_sent": notification_sent,
        "recipients_count": recipients_count,
    })

    return {
        "ok": True,
        "username": username,
        "old_name": old_name,
        "new_name": new_name,
        "password_changed": True,
        "signature_updated": sig_updated,
        "notification_sent": notification_sent,
        "recipients_count": recipients_count,
    }




@router.get("/quota/all")
async def get_all_quotas(request: Request, admin: dict = Depends(get_current_admin)):
    """Get quota usage for all mailboxes."""
    db = _db(request)
    users = await db.fetch("SELECT username FROM mailbox WHERE active = true ORDER BY username")
    quotas = {}
    for u in users:
        try:
            q = await get_quota(u["username"])
            quotas[u["username"]] = q
        except Exception:
            quotas[u["username"]] = {"used_bytes": 0, "limit_bytes": 0, "percent": 0, "messages": 0}
    return quotas

@router.post("/{username:path}/impersonate")
async def impersonate_mailbox(username: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Generate impersonation URL to open user mailbox in webmail."""
    from app.auth.jwt import create_token
    db = _db(request)
    
    # Verify mailbox exists
    row = await db.fetchrow("SELECT username, active FROM mailbox WHERE username = $1", username)
    if not row:
        raise HTTPException(404, "Buzón no encontrado")
    
    # Create admin token - the webmail /impersonate endpoint will verify it
    token, _ = create_token(admin["id"], admin["username"], admin["role"])
    
    await _audit(request, admin, "mailbox_impersonate", username)
    return {"token": token, "username": username}
