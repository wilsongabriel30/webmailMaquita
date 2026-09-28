"""Quitar una cuenta de los alias y grupos que entregaban en ella, sin tocar a nadie más."""


async def quitar_de_destinos(db, username: str) -> dict:
    username = username.strip().lower()
    filas = await db.fetch(
        "SELECT address, goto FROM alias WHERE address <> $1 AND $1 = ANY(string_to_array(replace(lower(goto), ' ', ''), ','))",
        username)
    editados, borrados = [], []
    for f in filas:
        quedan = [d.strip() for d in f["goto"].split(",") if d.strip() and d.strip().lower() != username]
        if quedan:
            await db.execute("UPDATE alias SET goto = $2, modified = NOW() WHERE address = $1", f["address"], ",".join(quedan))
            editados.append(f["address"])
        else:
            await db.execute("DELETE FROM alias WHERE address = $1", f["address"])
            borrados.append(f["address"])
    try:
        await db.execute("DELETE FROM mail_group_members WHERE lower(member_email) = $1", username)
    except Exception:
        pass  # instalación sin grupos
    return {"alias_editados": editados, "alias_borrados": borrados}
