import asyncpg


async def list_aliases(db: asyncpg.Pool, domain: str | None = None) -> list[dict]:
    if domain:
        rows = await db.fetch(
            """SELECT address, goto, domain, active, created, modified
               FROM alias
               WHERE domain = $1 AND address != goto
               ORDER BY address""",
            domain,
        )
    else:
        rows = await db.fetch("""SELECT address, goto, domain, active, created, modified
               FROM alias
               WHERE address != goto
               ORDER BY domain, address""")
    return [dict(r) for r in rows]


async def get_alias(db: asyncpg.Pool, address: str) -> dict | None:
    row = await db.fetchrow(
        "SELECT address, goto, domain, active, created, modified FROM alias WHERE address = $1",
        address,
    )
    return dict(row) if row else None


async def create_alias(
    db: asyncpg.Pool,
    address: str,
    goto: str,
    domain: str | None = None,
    active: bool = True,
) -> dict:
    if not domain:
        domain = address.split("@")[1]

    row = await db.fetchrow(
        """INSERT INTO alias (address, goto, domain, active)
           VALUES ($1, $2, $3, $4)
           RETURNING address, goto, domain, active, created, modified""",
        address,
        goto,
        domain,
        active,
    )
    return dict(row)


async def update_alias(
    db: asyncpg.Pool,
    address: str,
    goto: str | None = None,
    active: bool | None = None,
) -> dict | None:
    current = await db.fetchrow("SELECT * FROM alias WHERE address = $1", address)
    if not current:
        return None

    row = await db.fetchrow(
        """UPDATE alias SET
              goto = $2, active = $3, modified = NOW()
           WHERE address = $1
           RETURNING address, goto, domain, active, created, modified""",
        address,
        goto if goto is not None else current["goto"],
        active if active is not None else current["active"],
    )
    return dict(row) if row else None


async def delete_alias(db: asyncpg.Pool, address: str) -> bool:
    result = await db.execute("DELETE FROM alias WHERE address = $1", address)
    return result == "DELETE 1"
