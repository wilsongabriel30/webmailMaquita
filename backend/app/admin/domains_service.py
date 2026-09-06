import asyncpg


async def list_domains(db: asyncpg.Pool) -> list[dict]:
    rows = await db.fetch(
        """SELECT d.domain, d.description, d.aliases, d.mailboxes, d.maxquota,
                  d.quota, d.transport, d.backupmx, d.active, d.created, d.modified,
                  (SELECT count(*) FROM mailbox m WHERE m.domain = d.domain) as mailbox_count,
                  (SELECT count(*) FROM alias a WHERE a.domain = d.domain AND a.address != a.goto) as alias_count
           FROM domain d
           WHERE d.domain != 'ALL'
           ORDER BY d.domain"""
    )
    return [dict(r) for r in rows]


async def get_domain(db: asyncpg.Pool, domain: str) -> dict | None:
    row = await db.fetchrow(
        """SELECT d.*,
                  (SELECT count(*) FROM mailbox m WHERE m.domain = d.domain) as mailbox_count,
                  (SELECT count(*) FROM alias a WHERE a.domain = d.domain AND a.address != a.goto) as alias_count
           FROM domain d WHERE d.domain = $1""",
        domain,
    )
    return dict(row) if row else None


async def create_domain(
    db: asyncpg.Pool,
    domain: str,
    description: str = "",
    aliases: int = 0,
    mailboxes: int = 0,
    maxquota: int = 0,
    quota: int = 0,
    active: bool = True,
) -> dict:
    row = await db.fetchrow(
        """INSERT INTO domain (domain, description, aliases, mailboxes, maxquota, quota, active)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           RETURNING *""",
        domain,
        description,
        aliases,
        mailboxes,
        maxquota,
        quota,
        active,
    )
    return dict(row)


async def update_domain(
    db: asyncpg.Pool,
    domain: str,
    description: str | None = None,
    aliases: int | None = None,
    mailboxes: int | None = None,
    maxquota: int | None = None,
    quota: int | None = None,
    active: bool | None = None,
) -> dict | None:
    current = await db.fetchrow("SELECT * FROM domain WHERE domain = $1", domain)
    if not current:
        return None

    row = await db.fetchrow(
        """UPDATE domain SET
              description = $2, aliases = $3, mailboxes = $4,
              maxquota = $5, quota = $6, active = $7, modified = NOW()
           WHERE domain = $1
           RETURNING *""",
        domain,
        description if description is not None else current["description"],
        aliases if aliases is not None else current["aliases"],
        mailboxes if mailboxes is not None else current["mailboxes"],
        maxquota if maxquota is not None else current["maxquota"],
        quota if quota is not None else current["quota"],
        active if active is not None else current["active"],
    )
    return dict(row) if row else None


async def delete_domain(db: asyncpg.Pool, domain: str) -> bool:
    # Check no mailboxes remain
    count = await db.fetchval("SELECT count(*) FROM mailbox WHERE domain = $1", domain)
    if count > 0:
        raise ValueError(f"Cannot delete domain with {count} active mailbox(es)")

    result = await db.execute("DELETE FROM domain WHERE domain = $1", domain)
    return result == "DELETE 1"
