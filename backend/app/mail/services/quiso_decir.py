"""«¿Quiso decir…?»: cuando una búsqueda no encuentra nada, proponer la palabra bien escrita.

Lo que más se busca son personas, y lo que más se escribe mal son sus nombres («tiagho», «mishel»,
«loungg»). El vocabulario sale de los nombres y direcciones que la persona conoce: los buzones de
la casa, el directorio y su propia agenda. No se mira el contenido de ningún correo.
"""

from __future__ import annotations

import difflib
import logging
import re
import unicodedata

log = logging.getLogger(__name__)

MAX_SUGERENCIAS = 3
PARECIDO_MINIMO = 0.74
_PALABRA = re.compile(r"[^\W\d_]{3,}", re.UNICODE)


def _plano(texto: str) -> str:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def vocabulario(filas) -> dict[str, str]:
    """{palabra sin tildes: palabra tal como se escribe} a partir de (nombre, correo)."""
    voc: dict[str, str] = {}
    for nombre, correo in filas:
        for palabra in _PALABRA.findall(nombre or ""):
            voc.setdefault(_plano(palabra), palabra.lower())
        local = (correo or "").split("@")[0]
        for palabra in _PALABRA.findall(local.replace(".", " ").replace("_", " ")):
            voc.setdefault(_plano(palabra), palabra.lower())
    return voc


def sugerir(consulta: str, voc: dict[str, str]) -> list[str]:
    """Hasta MAX_SUGERENCIAS consultas corregidas; vacío si no hay nada mejor que proponer."""
    palabras = (consulta or "").split()
    if not palabras or not voc or len(palabras) > 6:
        return []
    claves = list(voc)
    opciones: list[list[str]] = []
    hubo_cambio = False
    for p in palabras:
        plano = _plano(p)
        if ":" in p or "@" in p or not _PALABRA.fullmatch(p) or plano in voc:
            opciones.append([p])
            continue
        # Lo escrito puede ser el principio de un nombre («contabilidadpuert»): no es un error.
        if len(plano) >= 4 and any(k.startswith(plano) for k in claves):
            opciones.append([p])
            continue
        # Casi nadie se equivoca en la primera letra: exigirla evita propuestas absurdas
        # («informe» → «conforme», «barbra» → «ibarra»).
        misma_inicial = [k for k in claves if k[0] == plano[0]]
        cerca = difflib.get_close_matches(
            plano, misma_inicial, n=MAX_SUGERENCIAS, cutoff=PARECIDO_MINIMO
        )
        if cerca:
            hubo_cambio = True
            opciones.append([voc[c] for c in cerca])
        else:
            opciones.append([p])
    if not hubo_cambio:
        return []
    salida: list[str] = []
    for i in range(MAX_SUGERENCIAS):
        frase = " ".join(o[min(i, len(o) - 1)] for o in opciones)
        if frase.lower() != consulta.lower() and frase not in salida:
            salida.append(frase)
    return salida


async def sugerencias(db, quien_busca: str, consulta: str) -> list[str]:
    if db is None or not (consulta or "").strip():
        return []
    try:
        filas = await db.fetch(
            """
            SELECT nombre, correo FROM (
                SELECT name AS nombre, username AS correo FROM mailbox WHERE active
                UNION ALL SELECT display_name, user_email FROM user_profiles
                UNION ALL SELECT display_name, username FROM user_preferences
                UNION ALL SELECT display_name, email FROM user_contacts
                          WHERE owner = $1 AND deleted_at IS NULL
            ) x WHERE correo LIKE '%@%' LIMIT 20000
            """,
            quien_busca,
        )
    except Exception as e:  # nunca estropea la búsqueda
        log.warning("quiso_decir: %r", e)
        return []
    return sugerir(consulta, vocabulario((f["nombre"], f["correo"]) for f in filas))
