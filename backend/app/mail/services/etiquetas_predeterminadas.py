"""Etiquetas predeterminadas de una cuenta nueva (09/11/2026).

Antes `GET /api/mail/labels` las insertaba al vuelo: un GET que escribe. Ahora las crea solo
`POST /api/mail/labels/predeterminadas`, que el navegador llama una vez cuando la lista llega vacía.
Idempotente: si la cuenta ya tiene alguna etiqueta (aunque sea una sola), no crea nada.
"""

PREDETERMINADAS: tuple[tuple[str, str], ...] = (
    ("Importante", "#d13438"),
    ("Trabajo", "#0078d4"),
    ("Personal", "#107c10"),
    ("Seguimiento", "#ca5010"),
    ("Proyecto", "#8764b8"),
)


async def crear_si_no_hay(db, owner: str) -> int:
    """Crea las predeterminadas si la cuenta no tiene ninguna etiqueta. Devuelve cuántas creó."""
    existentes = await db.fetchval(
        "SELECT COUNT(*) FROM user_labels WHERE owner = $1", owner
    )
    if existentes:
        return 0
    creadas = 0
    for nombre, color in PREDETERMINADAS:
        r = await db.execute(
            "INSERT INTO user_labels (owner, name, color) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            owner,
            nombre,
            color,
        )
        if str(r).endswith(" 1"):
            creadas += 1
    return creadas
