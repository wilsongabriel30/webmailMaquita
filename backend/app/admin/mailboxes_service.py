import asyncio

import asyncpg

from app.admin.doveadm_wrapper import generate_password_hash, get_quota


async def list_mailboxes(db: asyncpg.Pool, domain: str | None = None) -> list[dict]:
    if domain:
        rows = await db.fetch(
            """SELECT username, name, domain, quota, active, local_part,
                      phone, email_other, created, modified
               FROM mailbox WHERE domain = $1 ORDER BY username""",
            domain,
        )
    else:
        rows = await db.fetch(
            """SELECT username, name, domain, quota, active, local_part,
                      phone, email_other, created, modified
               FROM mailbox ORDER BY domain, username"""
        )
    return [dict(r) for r in rows]


async def get_mailbox(db: asyncpg.Pool, username: str) -> dict | None:
    row = await db.fetchrow(
        """SELECT username, name, domain, quota, active, local_part,
                  maildir, phone, email_other, created, modified
           FROM mailbox WHERE username = $1""",
        username,
    )
    if not row:
        return None

    result = dict(row)

    # Try to get quota usage from doveadm
    try:
        result["quota_usage"] = await get_quota(username)
    except Exception:
        result["quota_usage"] = None

    return result


async def create_mailbox(
    db: asyncpg.Pool,
    username: str,
    password: str,
    name: str = "",
    domain: str | None = None,
    quota: int = 0,
    active: bool = True,
) -> dict:
    if not domain:
        domain = username.split("@")[1]
    local_part = username.split("@")[0]
    maildir = f"{domain}/{local_part}/"

    # Hash password using doveadm
    password_hash = await generate_password_hash(password)

    row = await db.fetchrow(
        """INSERT INTO mailbox (username, password, name, maildir, quota, domain, local_part, active)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
           RETURNING username, name, domain, quota, active, local_part, created, modified""",
        username,
        password_hash,
        name,
        maildir,
        quota,
        domain,
        local_part,
        active,
    )

    # Also create self-alias (PostfixAdmin convention)
    await db.execute(
        """INSERT INTO alias (address, goto, domain, active)
           VALUES ($1, $1, $2, true)
           ON CONFLICT (address) DO NOTHING""",
        username,
        domain,
    )

    # GARANTIA anti-desincronizacion: la nueva clave DEBE autenticar por IMAP; si no, revertir.
    from app.auth.password import verify_imap

    if not await asyncio.to_thread(verify_imap, username, password):
        await db.execute("DELETE FROM alias WHERE address = $1", username)
        await db.execute("DELETE FROM mailbox WHERE username = $1", username)
        raise ValueError(
            "La contrasena no autentica por IMAP; cuenta NO creada. Reintenta."
        )

    return dict(row)


async def update_mailbox(
    db: asyncpg.Pool,
    username: str,
    name: str | None = None,
    password: str | None = None,
    quota: int | None = None,
    active: bool | None = None,
    phone: str | None = None,
    email_other: str | None = None,
) -> dict | None:
    current = await db.fetchrow("SELECT * FROM mailbox WHERE username = $1", username)
    if not current:
        return None

    new_password = current["password"]
    if password:
        new_password = await generate_password_hash(password)

    row = await db.fetchrow(
        """UPDATE mailbox SET
              name = $2, password = $3, quota = $4, active = $5,
              phone = $6, email_other = $7, modified = NOW()
           WHERE username = $1
           RETURNING username, name, domain, quota, active, local_part, phone, email_other, created, modified""",
        username,
        name if name is not None else current["name"],
        new_password,
        quota if quota is not None else current["quota"],
        active if active is not None else current["active"],
        phone if phone is not None else current["phone"],
        email_other if email_other is not None else current["email_other"],
    )
    # GARANTIA anti-desincronizacion: si se cambio la clave, confirmar IMAP; si no, revertir.
    if password and row:
        from app.auth.password import verify_imap

        if not await asyncio.to_thread(verify_imap, username, password):
            await db.execute(
                "UPDATE mailbox SET password = $2 WHERE username = $1",
                username,
                current["password"],
            )
            raise ValueError(
                "La contrasena no se aplico (no autentica por IMAP). Se revirtio; reintenta."
            )

    return dict(row) if row else None


async def delete_mailbox(db: asyncpg.Pool, username: str) -> bool:
    domain = username.split("@")[1]

    # Delete self-alias
    await db.execute("DELETE FROM alias WHERE address = $1 AND goto = $1", username)
    # Delete any aliases pointing to this mailbox
    await db.execute(
        "DELETE FROM alias WHERE goto LIKE $1",
        f"%{username}%",
    )
    # Delete mailbox
    result = await db.execute("DELETE FROM mailbox WHERE username = $1", username)
    return result == "DELETE 1"


async def toggle_active(db: asyncpg.Pool, username: str) -> dict | None:
    row = await db.fetchrow(
        """UPDATE mailbox SET active = NOT active, modified = NOW()
           WHERE username = $1
           RETURNING username, name, domain, quota, active""",
        username,
    )
    return dict(row) if row else None
