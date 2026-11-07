"""Salvaguarda determinista: el texto que la IA entrega debe estar en alfabeto latino.

Los modelos pequeños (p. ej. qwen2.5:7b) a veces derivan a otro idioma a mitad de la
respuesta y escriben en chino, japonés, cirílico, etc. Para un correo en español eso nunca es
correcto, así que se detecta sin ambigüedad (por la escritura de cada letra, no por idioma):

- `tiene_ajeno(texto)`: True si hay alguna letra de un alfabeto no latino o signos de
  puntuación CJK (「」。，、 y formas de ancho completo).
- `limpiar(texto)`: quita las oraciones o líneas que contienen esos caracteres. Si no queda
  nada útil, devuelve cadena vacía (cada función de IA tiene ya su respuesta de reserva).
- `generar(llamar, temperatura, funcion)`: llama al modelo; si la salida trae caracteres
  ajenos, reintenta UNA vez con temperatura más baja. Devuelve la salida (la limpieza final
  la hace `estilo_institucional.institucionalizar`, que se aplica a todo texto visible).

Se permiten: ASCII, Latin-1 (á, ñ, ü, ¿, ¡, º, ª), los latinos extendidos, signos generales
de puntuación y símbolos (comillas tipográficas, «», guiones, €, emojis).
"""

import logging
import re
import unicodedata

logger = logging.getLogger("ai.alfabeto")

TEMPERATURA_REINTENTO = 0.2


def _es_ajeno(c: str) -> bool:
    o = ord(c)
    if o <= 0x024F or 0x1E00 <= o <= 0x1EFF:  # ASCII, Latin-1 y latinos extendidos
        return False
    if (
        0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF
    ):  # puntuación CJK y ancho completo
        return True
    if unicodedata.category(c).startswith("L"):
        return not unicodedata.name(c, "").startswith("LATIN")
    return False


def tiene_ajeno(texto) -> bool:
    """True si el texto contiene letras de un alfabeto no latino o puntuación CJK."""
    return isinstance(texto, str) and any(_es_ajeno(c) for c in texto)


# Oraciones o líneas: se corta tras . ! ? (también los CJK) y en cada salto de línea.
_CORTE = re.compile(r"(?<=[.!?。！？\n])")


def limpiar(texto):
    """Quita las oraciones/líneas con caracteres ajenos. Sin ellos, devuelve el texto igual."""
    if not tiene_ajeno(texto):
        return texto
    trozos = [t for t in _CORTE.split(texto) if t and not tiene_ajeno(t)]
    limpio = re.sub(r"[ \t]{2,}", " ", "".join(trozos)).strip()
    # Sin letras útiles (p. ej. solo signos) no se entrega nada: la función usa su reserva.
    if len(re.sub(r"\W", "", limpio)) < 3:
        limpio = ""
    logger.warning(
        "IA_ALFABETO_LIMPIEZA quitados=%d caracteres, quedan=%d",
        len(texto) - len(limpio),
        len(limpio),
    )
    return limpio


async def generar(llamar, temperatura: float, funcion: str = ""):
    """`await llamar(t)` con temperatura `t`; un reintento más frío si hay alfabeto ajeno."""
    texto = await llamar(temperatura)
    if not tiene_ajeno(texto):
        return texto
    t2 = min(temperatura, TEMPERATURA_REINTENTO)
    logger.warning(
        "IA_ALFABETO_AJENO funcion=%s temperatura=%.2f: se reintenta con %.2f",
        funcion,
        temperatura,
        t2,
    )
    texto2 = await llamar(t2)
    if tiene_ajeno(texto2):
        logger.warning(
            "IA_ALFABETO_AJENO_PERSISTE funcion=%s: se quitan los fragmentos", funcion
        )
    return texto2
