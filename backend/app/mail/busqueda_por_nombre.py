"""Buscar correos por el NOMBRE de la persona, aunque el correo no lo traiga (06/11/2026).

Un correo puede llegar como «Analista Planificación y Procesos <analista.pp@…>» o solo con la
dirección; quien busca «Gissela» no lo encontraba porque IMAP solo mira el texto de las cabeceras.
Aquí se traduce el texto libre de la búsqueda a las direcciones cuyo dueño se llama así (buzones,
directorio de nómina, nombre de preferencias y la agenda de quien busca) y la búsqueda incluye
también lo enviado por, para o con copia a esas direcciones. Sin tildes y sin mayúsculas.
"""

from __future__ import annotations

import logging
import unicodedata

log = logging.getLogger(__name__)

MAXIMO = 8


def _sin_tildes(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto)
    return "".join(c for c in t if not unicodedata.combining(c))


def texto_libre(consulta: str) -> str:
    """Solo las palabras sueltas (sin operadores como «from:» ni exclusiones)."""
    palabras = [
        w for w in (consulta or "").split() if ":" not in w and not w.startswith("-")
    ]
    return " ".join(palabras).strip().strip('"').strip()


async def direcciones_de_nombre(db, quien_busca: str, consulta: str) -> list[str]:
    texto = texto_libre(consulta)
    if len(texto) < 3 or "@" in texto or db is None:
        return []
    # Cada palabra por separado: «ronald leon» encuentra «Ronald Xavier León» (13/11/2026).
    palabras = [p for p in _sin_tildes(texto.lower()).split() if len(p) >= 2][:4]
    if not palabras:
        return []
    patrones = ["%" + p.replace("%", "").replace("_", "") + "%" for p in palabras]
    try:
        filas = await db.fetch(
            """
            SELECT DISTINCT lower(trim(correo)) AS correo FROM (
                SELECT username AS correo, name AS nombre FROM mailbox WHERE active
                UNION ALL SELECT user_email, display_name FROM user_profiles
                UNION ALL SELECT username, display_name FROM user_preferences
                UNION ALL SELECT email, display_name FROM user_contacts
                          WHERE owner = $2 AND deleted_at IS NULL
            ) x
            WHERE nombre IS NOT NULL AND correo LIKE '%@%'
              AND translate(lower(nombre), 'áéíóúüñàèìòù', 'aeiouunaeiou') LIKE ALL($1::text[])
            LIMIT $3
            """,
            patrones,
            quien_busca,
            MAXIMO,
        )
    except Exception as e:  # la búsqueda nunca falla por esto
        log.warning("busqueda_por_nombre: %r", e)
        return []
    return [f["correo"] for f in filas]
