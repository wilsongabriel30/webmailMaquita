"""Nombre con el que sale el correo («Nombre <correo>»).

06/11/2026: antes solo se usaba user_preferences.display_name y 11 de 20 personas no lo tenían
configurado: su correo salía solo con la dirección. Ahora, si la persona no puso un nombre en sus
preferencias, se usa el del buzón (mailbox.name, el mismo que tenía en Zimbra).
"""


async def nombre_para_envio(db, username: str) -> str:
    row = await db.fetchrow(
        """
        SELECT COALESCE(TRIM(p.display_name), '') AS preferido,
               COALESCE(TRIM(m.name), '') AS buzon,
               COALESCE(m.local_part, '') AS local_part
        FROM (SELECT $1::text AS u) x
        LEFT JOIN user_preferences p ON p.username = x.u
        LEFT JOIN mailbox m ON m.username = x.u
        """,
        username,
    )
    if not row:
        return ""
    if row["preferido"]:
        return row["preferido"]
    buzon = " ".join((row["buzon"] or "").split())
    # «info», «webmaster»…: el nombre del buzón es solo el usuario; no aporta nada.
    if buzon and buzon.lower() not in (row["local_part"].lower(), username.lower()):
        return buzon
    return ""
