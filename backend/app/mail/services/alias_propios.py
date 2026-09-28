"""Alias personales de una cuenta: otras direcciones que entregan solo en su buzón.

Una misma persona puede recibir correo con direcciones de varios dominios del servidor.
«Responder a todos» las necesita para no escribirle a ella misma.

No cuentan las listas (alias que entregan a varias personas): responder a la lista es
escribir al grupo, no a uno mismo.
"""


async def alias_de(db, email: str) -> list[str]:
    try:
        filas = await db.fetch(
            """SELECT lower(address) AS direccion FROM alias
               WHERE active AND lower(btrim(goto)) = lower($1) AND lower(address) <> lower($1)
               ORDER BY 1""",
            email,
        )
    except Exception:
        return []
    return [f["direccion"] for f in filas]
