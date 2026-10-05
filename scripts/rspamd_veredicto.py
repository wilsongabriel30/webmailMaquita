"""Segunda opinión de Rspamd para los veredictos por indicios débiles.

El filtro por reglas suma puntos por indicios que, solos, no prueban nada:
muchos enlaces, falta de DKIM, Reply-To distinto, solo HTML... Un hilo de
correo entre empresas con varias firmas llega al umbral sin ser publicidad.
Rspamd ya analizó ese mismo correo con mucha más información (reputación,
Bayes, SPF/DKIM/ARC); si lo da por claramente legítimo (puntuación < 0) y
el filtro por reglas solo tiene indicios débiles, el correo se entrega en la
bandeja de entrada.

No se aplica nunca si hay virus, listas negras o grises, palabras clave,
adjuntos sospechosos, enlaces acortados o con IP, ni si la puntuación llega
al tope: esos casos siguen yendo a no deseado como siempre.
"""

import re

# Rspamd considera spam desde +6 (add header) y rechaza desde +20. Se exige una
# puntuación negativa: un 0,00 exacto solo dice que no encontró nada, ni bueno ni malo.
RSPAMD_LEGITIMO_MAX = -0.01
# Por encima de este total ya no son «indicios sueltos».
TOPE_INDICIOS_DEBILES = 6

INDICIOS_DEBILES = (
    "exceso-links",
    "muchos-links",
    "sin-dkim",
    "sin-dkim-spf",
    "reply-to-diferente",
    "solo-html",
    "subject-vacio",
    "varios-destinatarios",
    "precedence-bulk",
    "neurona",
)

_PUNTUACION = re.compile(r"\[\s*(-?\d+(?:\.\d+)?)\s*/\s*\d+(?:\.\d+)?\s*\]")


def puntuacion_rspamd(msg):
    """Puntuación de X-Spamd-Result, o None si falta o es dudosa.

    Rspamd quita las cabeceras X-Spamd-Result que traiga el correo y pone la
    suya; si aun así hay más de una, no se confía en ninguna.
    """
    try:
        cabeceras = msg.get_all("X-Spamd-Result") or []
        if len(cabeceras) != 1:
            return None
        m = _PUNTUACION.search(str(cabeceras[0]))
        return float(m.group(1)) if m else None
    except Exception:
        return None


def solo_indicios_debiles(razones):
    """True si todas las razones que suman puntos son indicios débiles."""
    for razon in razones:
        nombre = re.split(r"[(:]", str(razon), maxsplit=1)[0].strip()
        if nombre in INDICIOS_DEBILES:
            continue
        # Los descuentos (lista blanca, correo propio) no agravan nada.
        if nombre.startswith(("whitelist-dominio", "propio-")):
            continue
        return False
    return True


def rescatar_por_rspamd(msg, score, razones):
    """(True, puntuación) si Rspamd desmiente un veredicto por indicios débiles."""
    if score >= TOPE_INDICIOS_DEBILES or not solo_indicios_debiles(razones):
        return False, None
    puntuacion = puntuacion_rspamd(msg)
    if puntuacion is None or puntuacion > RSPAMD_LEGITIMO_MAX:
        return False, puntuacion
    return True, puntuacion
