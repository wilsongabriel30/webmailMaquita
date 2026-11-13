"""Texto libre de la búsqueda: cada palabra por separado y en cualquier parte del correo.

Antes todo lo escrito iba como una sola cadena a cada campo («ana factura» tenía que estar junto
en el remitente, o junto en el asunto…). Quien recordaba el nombre de la persona y una palabra del
asunto no encontraba nada. Ahora cada palabra debe aparecer en el correo, pero cada una puede estar
en un sitio distinto: remitente, destinatarios, copia, asunto o —con índice de texto— el cuerpo.
Lo que va entre comillas sigue siendo una frase.

Dos rarezas del índice de texto de Dovecot que aquí se compensan (comprobadas el 13/11/2026):

- En remitente, destinatarios y copia el índice NO quita las tildes (en asunto y cuerpo sí):
  «raices» no encontraba a «Raíces», ni «barbara» a «Bárbara». Para esos campos se buscan también
  las variantes con tilde y con eñe de cada palabra (`variantes`).
- Un trozo de una sola letra anula el término entero: «T-53» daba cero aunque el asunto lo
  tuviera. Los términos se parten por sus signos y se descartan los trozos de una letra.

No se usa el criterio TEXT de IMAP: mira todas las cabeceras (también las técnicas, como las de
tránsito), y una palabra como el nombre de un proveedor de correo sale en casi todo el buzón.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable

# Palabras que no distinguen un correo de otro. Solo se descartan si queda algo más que buscar.
VACIAS = frozenset(
    "a al con de del el en la las lo los o para por que un una y e the of and to for in on".split()
)
MAX_TERMINOS = 8
_ALFANUMERICO = re.compile(r"\w", re.UNICODE)
_BORDES = "\"'«»“”‘’()[]{}<>¿?¡!,;"
_SEPARADORES = re.compile(r"[^\w@.]+|(?<![\w])\.|\.(?![\w])", re.UNICODE)
_CAMPOS_DE_PERSONA = frozenset(("FROM", "TO", "CC"))
_TILDES = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}
MAX_VARIANTES = 16


def _sin_tildes(texto: str) -> str:
    """Sin tildes ni diéresis, pero conservando la eñe."""
    marca = "\x00"
    plano = unicodedata.normalize("NFD", texto.replace("ñ", marca).replace("Ñ", marca))
    return "".join(c for c in plano if not unicodedata.combining(c)).replace(marca, "ñ")


def _partir(termino: str) -> str:
    """«T-53» → «53»; «informe_final» → «informe final». Las direcciones de correo no se tocan."""
    if "@" in termino:
        return termino
    trozos = [x for x in _SEPARADORES.split(termino.replace("_", " ")) if x]
    utiles = [x for x in trozos if len(x) >= 2]
    return " ".join(utiles or trozos)


def variantes(termino: str) -> list[str]:
    """La palabra tal cual, sin tildes y con cada tilde o eñe posible (una por palabra).

    «raices» → raices, ráices, raíces, raicés. Solo para palabras sueltas de letras: en una frase,
    un número o una dirección de correo no hay tilde que adivinar.
    """
    if not termino.isalpha() or len(termino) < 3:
        return [termino]
    base = _sin_tildes(termino.lower())
    con_enie = [base] + [
        base[:i] + "ñ" + base[i + 1 :] for i, c in enumerate(base) if c == "n"
    ]
    salida = [termino.lower()]
    for b in con_enie:
        for v in [b] + [
            b[:i] + _TILDES[c] + b[i + 1 :] for i, c in enumerate(b) if c in _TILDES
        ]:
            if v not in salida:
                salida.append(v)
    return salida[:MAX_VARIANTES]


def terminos(palabras: Iterable[str]) -> list[str]:
    """Palabras y frases útiles, sin repetir y sin signos sueltos (un guion, «(1)» → «1»)."""
    limpios: list[str] = []
    for p in palabras:
        t = _partir((p or "").strip().strip(_BORDES).strip())
        if (
            t
            and _ALFANUMERICO.search(t)
            and t.lower() not in (x.lower() for x in limpios)
        ):
            limpios.append(t)
    con_peso = [
        t for t in limpios if " " in t or (len(t) >= 2 and t.lower() not in VACIAS)
    ]
    return (con_peso or limpios)[:MAX_TERMINOS]


def _en_campos(
    termino: str, campos: tuple[str, ...], comillas: Callable[[str], str]
) -> list[str]:
    """`OR OR FROM "x" TO "x" SUBJECT "x"`: el término en cualquiera de los campos."""
    claves: list[str] = []
    formas = variantes(termino)
    for c in campos:
        for f in formas if c in _CAMPOS_DE_PERSONA else [termino]:
            claves.append(f"{c} {comillas(f)}")
    return ["OR"] * (len(claves) - 1) + claves


def con_variantes(
    campo: str, valor: str, base: list[str], comillas: Callable[[str], str]
) -> list[str]:
    """Antepone a `base` (un criterio completo) las variantes con tilde de `valor` en ese campo.

    Para los operadores `de:`, `para:` y `copia:`: `de:barbara` encuentra también a «Bárbara».
    """
    salida = list(base)
    for forma in variantes(valor)[1:]:
        salida = ["OR", f"{campo} {comillas(forma)}"] + salida
    return salida


def criterio(
    palabras: Iterable[str],
    con_cuerpo: bool,
    direcciones: Iterable[str],
    comillas: Callable[[str], str],
) -> list[str]:
    """Criterios IMAP para el texto libre. Lista vacía si no queda nada que buscar."""
    lista = terminos(palabras)
    if not lista:
        return []
    if len(lista) == 1 and not con_cuerpo:
        campos: tuple[str, ...] = (
            "FROM",
            "TO",
            "SUBJECT",
        )  # el caso de siempre, tal como era
    else:
        campos = ("FROM", "TO", "CC", "SUBJECT") + (("BODY",) if con_cuerpo else ())
    libre: list[str] = []
    for t in lista:
        libre += _en_campos(t, campos, comillas)
    direcciones = list(direcciones or [])[:8]
    if not direcciones:
        return libre
    # También lo enviado por, para o con copia a las personas que se llaman así.
    grupo = ["(" + " ".join(libre) + ")"] if len(lista) > 1 else libre
    for d in direcciones:
        for campo in ("FROM", "TO", "CC"):
            grupo = ["OR"] + grupo + [f"{campo} {comillas(d)}"]
    return grupo
