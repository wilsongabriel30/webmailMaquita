"""Idioma de las funciones de IA: español (por defecto) o inglés.

La IA responde en el idioma del correo o de la conversación: inglés si el correo al que se
responde, lo que escribe la persona o su pregunta están en inglés; español en cualquier otro
caso (es el idioma de la institución). La detección es ligera y determinista: cuenta palabras
muy frecuentes de cada idioma (artículos, preposiciones, fórmulas de correo). No usa modelos
ni servicios externos.

- `detectar(texto)`: «es», «en» o None si el texto es corto o ambiguo.
- `normalizar(valor)`: «es-EC», «es», «en-US», «en»… → «es» / «en» (otro valor → None).
- `elegir(*candidatos)`: el primero que no sea None; si ninguno, español.
- `regla(idioma)`: frase para la instrucción de sistema («Escribe solo en español.»).

El frontend tiene la misma lógica en `frontend/src/lib/idiomaTexto.ts` (corrector ortográfico):
si se cambia una lista aquí, conviene cambiarla allá.
"""

import re
from typing import Optional

ES = "es"
EN = "en"

# Palabras frecuentes que casi solo existen en un idioma. Se excluyen las que valen en los dos
# («a», «me», «no», «he», «son», «solo», «final»…).
_ES = frozenset("""
    de la que el en y los las del se por un una para con su al lo como más mas pero sus le ya
    o este esta estos estas ese esa eso esto porque entre cuando muy sin sobre también tambien
    hasta hay donde desde todo todos todas nos durante uno les ni otros otras otro otra ante
    ellos ellas antes algunos qué unos yo él tanto mucho muchos nada algo nosotros mi mis tu tus
    usted ustedes es está están esta estan gracias saludos estimado estimada estimados
    estimadas buenos buenas días dias tardes noches favor adjunto adjunta reunión reunion hola
    querido querida queridos queridas cordial atentamente le les cual cuál quien quién dónde
    cómo como señor señora compañeros compañeras equipo informe semana mañana hoy
    """.split())
_EN = frozenset("""
    the and of to in is you that it for on with as are this be at have from or by we your
    will can our not but they all would there their what so if about which when do please
    thank thanks dear regards best hello hi meeting attached could should let know i my an
    was were been has had any us these those kind sincerely looking forward team colleagues
    attend schedule report week today tomorrow morning afternoon hope well find following
    send sent here how who where why yes need would also just more some into than then them
    """.split())
# Saludos de apertura: deciden aunque el texto sea muy corto («Dear», «Estimad»).
_INICIO_EN = re.compile(
    r"^\s*(?:dear|hello|hi|good (?:morning|afternoon|evening)|greetings)\b", re.I
)
_INICIO_ES = re.compile(
    r"^\s*(?:estimad|querid|apreciad|buen[oa]s (?:d[ií]as|tardes|noches)|hola\b|"
    r"se[ñn]or|distinguid|reciba|por medio)",
    re.I,
)
_RUIDO = re.compile(r"(?m)^>.*$|https?://\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PALABRA = re.compile(r"[a-záéíóúüñ']+", re.I)
_DIACRITICOS_ES = re.compile(r"[ñáéíóú¿¡]", re.I)
_MAX = 4000  # basta con el comienzo del texto


def _puntos(texto: str):
    palabras = [p.strip("'") for p in _PALABRA.findall(texto.lower())]
    es = sum(1 for p in palabras if p in _ES)
    en = sum(1 for p in palabras if p in _EN)
    es += min(3, len(_DIACRITICOS_ES.findall(texto)))  # ñ, tildes, ¿ ¡
    return es, en


def detectar(texto) -> Optional[str]:
    """«es», «en» o None. Se ignoran las líneas citadas («>»), enlaces y direcciones."""
    if not isinstance(texto, str):
        return None
    t = _RUIDO.sub(" ", texto[:_MAX])
    es, en = _puntos(t)
    if en >= 2 and en > 1.5 * es:
        return EN
    if es >= 2 and es > 1.5 * en:
        return ES
    if es + en <= 2:  # texto muy corto: decide el saludo con que empieza
        if _INICIO_EN.match(t):
            return EN
        if _INICIO_ES.match(t):
            return ES
    return None


def normalizar(valor) -> Optional[str]:
    """«es-EC» → «es», «en-US» → «en»; cualquier otro valor → None."""
    if not isinstance(valor, str):
        return None
    base = valor.strip().lower().replace("_", "-").split("-")[0]
    return base if base in (ES, EN) else None


def elegir(*candidatos) -> str:
    """El primer idioma conocido de la lista (ya normalizados o no); si ninguno, español."""
    for c in candidatos:
        n = normalizar(c)
        if n:
            return n
    return ES


def regla(idioma: str) -> str:
    """Regla de idioma para la instrucción de sistema."""
    return "Write only in English." if idioma == EN else "Escribe solo en español."
