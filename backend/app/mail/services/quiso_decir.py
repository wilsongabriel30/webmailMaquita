"""«¿Quiso decir…?»: cuando una búsqueda no encuentra nada, proponer la palabra bien escrita.

Lo que más se busca son personas, y lo que más se escribe mal son sus nombres («tiagho», «mishel»,
«loungg»). El vocabulario sale de los nombres y direcciones que la persona conoce: los buzones de
la casa, el directorio y su propia agenda. No se mira el contenido de ningún correo.

Varias palabras (13/11/2026): cada palabra se corrige por separado y se propone la frase entera.
Si hay varias correcciones posibles, va primero la combinación que es el nombre de UNA persona
(«fernado pachco» → «fernando pacheco» antes que mezclar el nombre de uno con el apellido de
otro). Las comillas y los signos pegados a una palabra se conservan.
"""

from __future__ import annotations

import difflib
import itertools
import logging
import re
import unicodedata

log = logging.getLogger(__name__)

MAX_SUGERENCIAS = 3
PARECIDO_MINIMO = 0.74
MAX_PALABRAS = 6
_PALABRA = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
_SIGNOS = "\"'«»“”‘’()[]¿?¡!,;."


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


def personas(filas) -> list[frozenset[str]]:
    """Las palabras (sin tildes) del nombre y de la dirección de cada persona conocida."""
    return [frozenset(vocabulario([fila])) for fila in filas]


def _nucleo(palabra: str) -> tuple[str, str, str]:
    """(signos de delante, palabra, signos de detrás): «"fernado» → («"», «fernado», «»)."""
    sin_izquierda = palabra.lstrip(_SIGNOS)
    centro = sin_izquierda.rstrip(_SIGNOS)
    delante = palabra[: len(palabra) - len(sin_izquierda)]
    return delante, centro, sin_izquierda[len(centro) :]


def _opciones(palabra: str, voc: dict[str, str], claves: list[str]) -> list[str]:
    """Las formas correctas (claves sin tildes) de una palabra mal escrita; vacío si está bien."""
    plano = _plano(palabra)
    if not _PALABRA.fullmatch(palabra) or plano in voc:
        return []
    # Lo escrito puede ser el principio de un nombre («contabilidadpuert»): no es un error.
    if len(plano) >= 4 and any(k.startswith(plano) for k in claves):
        return []
    # Casi nadie se equivoca en la primera letra: exigirla evita propuestas absurdas
    # («informe» → «conforme», «barbra» → «ibarra»).
    misma_inicial = [k for k in claves if k[0] == plano[0]]
    return difflib.get_close_matches(
        plano, misma_inicial, n=MAX_SUGERENCIAS, cutoff=PARECIDO_MINIMO
    )


def sugerir(
    consulta: str, voc: dict[str, str], gente: list[frozenset[str]] | None = None
) -> list[str]:
    """Hasta MAX_SUGERENCIAS consultas corregidas; vacío si no hay nada mejor que proponer.

    `gente` (de `personas`) sirve para ordenar las frases de varias palabras: primero las que
    son el nombre de una misma persona.
    """
    palabras = (consulta or "").split()
    if not palabras or not voc or len(palabras) > MAX_PALABRAS:
        return []
    claves = list(voc)
    # Por palabra: (signos de delante, formas posibles como claves o None si no se toca, detrás).
    piezas: list[tuple[str, list[str] | None, str]] = []
    hubo_cambio = False
    for p in palabras:
        delante, centro, detras = _nucleo(p)
        cerca = [] if ":" in p or "@" in p else _opciones(centro, voc, claves)
        if cerca:
            hubo_cambio = True
            piezas.append((delante, cerca, detras))
        else:
            piezas.append((p, None, ""))
    if not hubo_cambio:
        return []
    # Palabras bien escritas que también son de un nombre: cuentan para saber de quién se habla.
    fijas = {
        _plano(_nucleo(p)[1])
        for p, (_, formas, _) in zip(palabras, piezas)
        if formas is None and _plano(_nucleo(p)[1]) in voc
    }
    combinaciones = []
    for elegidas in itertools.product(
        *[range(len(formas)) if formas else (0,) for _, formas, _ in piezas]
    ):
        nombres = fijas | {
            formas[i] for i, (_, formas, _) in zip(elegidas, piezas) if formas
        }
        de_una_persona = (
            len(nombres) >= 2 and gente is not None and any(nombres <= g for g in gente)
        )
        # Primero el nombre de una persona; después, las formas más parecidas a lo escrito.
        combinaciones.append(
            (not de_una_persona, max(elegidas), sum(elegidas), elegidas)
        )
    salida: list[str] = []
    for *_, elegidas in sorted(combinaciones):
        frase = " ".join(
            delante + voc[formas[i]] + detras if formas else delante
            for i, (delante, formas, detras) in zip(elegidas, piezas)
        )
        if frase.lower() != consulta.lower() and frase not in salida:
            salida.append(frase)
        if len(salida) == MAX_SUGERENCIAS:
            break
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
    pares = [(f["nombre"], f["correo"]) for f in filas]
    return sugerir(consulta, vocabulario(pares), personas(pares))
