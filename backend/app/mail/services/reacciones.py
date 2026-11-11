"""Reacciones a un correo (👍 ❤️ 🎉 😂 😮 😢), como en Outlook (11/11/2026).

La reacción no modifica el correo ni genera otro: se guarda junto al `Message-ID`, así que la ven
todas las personas de este servidor que tienen ese mismo correo (quien lo envió y quienes lo
recibieron). Una reacción por persona y correo: elegir otra la cambia; elegir la misma la quita.
"""

from __future__ import annotations

from email.utils import getaddresses

CATALOGO = ("👍", "❤️", "🎉", "😂", "😮", "😢")


def emoji_valido(emoji: str) -> bool:
    return emoji in CATALOGO


async def alternar(db, message_id: str, usuario: str, emoji: str) -> str:
    """Pone, cambia o quita la reacción de la persona. Devuelve «puesta», «cambiada» o «quitada»."""
    actual = await db.fetchval(
        "SELECT emoji FROM mail_reacciones WHERE message_id = $1 AND usuario = $2",
        message_id,
        usuario,
    )
    if actual == emoji:
        await db.execute(
            "DELETE FROM mail_reacciones WHERE message_id = $1 AND usuario = $2",
            message_id,
            usuario,
        )
        return "quitada"
    await db.execute(
        """INSERT INTO mail_reacciones (message_id, usuario, emoji) VALUES ($1, $2, $3)
           ON CONFLICT (message_id, usuario) DO UPDATE SET emoji = EXCLUDED.emoji, creado = now()""",
        message_id,
        usuario,
        emoji,
    )
    return "cambiada" if actual else "puesta"


async def fijar(
    db, message_id: str, usuario: str, emoji: str | None, nombre: str = ""
) -> str:
    """Deja la reacción de la persona exactamente como se indica (None = sin reacción).

    La usa el aviso que llega de otro servidor: allí ya se decidió el estado final.
    """
    actual = await db.fetchval(
        "SELECT emoji FROM mail_reacciones WHERE message_id = $1 AND usuario = $2",
        message_id,
        usuario,
    )
    if emoji is None:
        await db.execute(
            "DELETE FROM mail_reacciones WHERE message_id = $1 AND usuario = $2",
            message_id,
            usuario,
        )
        return "quitada"
    await db.execute(
        """INSERT INTO mail_reacciones (message_id, usuario, emoji, nombre) VALUES ($1, $2, $3, $4)
           ON CONFLICT (message_id, usuario)
           DO UPDATE SET emoji = EXCLUDED.emoji, nombre = EXCLUDED.nombre, creado = now()""",
        message_id,
        usuario,
        emoji,
        nombre or None,
    )
    return "cambiada" if actual else "puesta"


async def resumen(db, message_id: str, usuario: str) -> list[dict]:
    """Reacciones del correo agrupadas por emoji, en el orden del catálogo."""
    filas = await db.fetch(
        """SELECT r.usuario, r.emoji, COALESCE(NULLIF(m.name, ''), NULLIF(r.nombre, ''), r.usuario) AS nombre
             FROM mail_reacciones r LEFT JOIN mailbox m ON m.username = r.usuario
            WHERE r.message_id = $1 ORDER BY r.creado""",
        message_id,
    )
    grupos: dict[str, dict] = {}
    for f in filas:
        g = grupos.setdefault(
            f["emoji"], {"emoji": f["emoji"], "total": 0, "personas": [], "mia": False}
        )
        g["total"] += 1
        g["personas"].append(f["nombre"])
        if f["usuario"] == usuario:
            g["mia"] = True
    orden = {e: i for i, e in enumerate(CATALOGO)}
    return sorted(grupos.values(), key=lambda g: orden.get(g["emoji"], len(orden)))


def participantes(msg) -> tuple[str, set[str]]:
    """(autor, todas las direcciones de De/Para/CC) del correo, en minúsculas."""
    autor = ""
    de = getaddresses([str(msg.get("From", ""))])
    if de and "@" in de[0][1]:
        autor = de[0][1].strip().lower()
    todos = {
        d.strip().lower()
        for _, d in getaddresses(
            [str(v) for c in ("From", "To", "Cc") for v in (msg.get_all(c) or [])]
        )
        if "@" in d
    }
    return autor, todos


async def cuentas_locales(db, direcciones: set[str]) -> list[str]:
    """De esas direcciones, las que son buzones activos de este servidor."""
    if not direcciones:
        return []
    filas = await db.fetch(
        "SELECT username FROM mailbox WHERE active = true AND username = ANY($1::text[])",
        sorted(direcciones),
    )
    return [f["username"] for f in filas]


async def nombre_de(db, usuario: str) -> str:
    nombre = await db.fetchval("SELECT name FROM mailbox WHERE username = $1", usuario)
    return (nombre or "").strip() or usuario
