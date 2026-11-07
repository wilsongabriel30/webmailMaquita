"""Lectura de respuestas `UID FETCH` de aioimaplib (con literales) a diccionarios.

aioimaplib entrega la respuesta como lista: líneas `bytes` y, tras cada línea que termina en
`{n}`, el literal (n bytes) en el elemento siguiente. Aquí se rehace el flujo IMAP y se lee
con un analizador de listas para obtener, por mensaje, {"UID": "5", "BODYSTRUCTURE": [...],
"BODY[HEADER.FIELDS (FROM)]": b"...", "BODY[1]<0>": b"..."}.
"""

import re

_RE_LITERAL = re.compile(rb"\{(\d+)\}\s*$")


class Literal(bytes):
    """Contenido de un literal IMAP (se distingue de los átomos y cadenas)."""


def _a_bytes(elemento) -> bytes:
    if isinstance(elemento, (bytes, bytearray)):
        return bytes(elemento)
    return str(elemento).encode("utf-8", "replace")


def _flujo(lineas) -> list:
    """Lista alterna de trozos de texto (bytes) y Literal."""
    trozos: list = []
    esperando = False
    for el in lineas or ():
        b = _a_bytes(el)
        if esperando:
            trozos.append(Literal(b))
            esperando = False
            continue
        m = _RE_LITERAL.search(b)
        if m:
            trozos.append(b[: m.start()])
            esperando = True
        else:
            trozos.append(b + b"\n")
    return trozos


def _tokens_texto(t: str):
    i, n = 0, len(t)
    while i < n:
        c = t[i]
        if c.isspace():
            i += 1
        elif c in "()":
            yield c
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while j < n and t[j] != '"':
                if t[j] == "\\" and j + 1 < n:
                    j += 1
                buf.append(t[j])
                j += 1
            yield ("Q", "".join(buf))
            i = j + 1
        else:
            j, prof = i, 0
            while j < n:
                cj = t[j]
                if cj == "[":
                    prof += 1
                elif cj == "]":
                    prof -= 1
                elif prof <= 0 and (cj.isspace() or cj in "()"):
                    break
                j += 1
            atomo = t[i:j]
            yield None if atomo.upper() == "NIL" else ("A", atomo)
            i = j


def tokens(lineas) -> list:
    salida = []
    for trozo in _flujo(lineas):
        if isinstance(trozo, Literal):
            salida.append(trozo)
        else:
            salida.extend(_tokens_texto(trozo.decode("utf-8", "replace")))
    return salida


def _valor(t):
    if isinstance(t, tuple):
        return t[1]
    return t  # None o Literal


def _lista(toks: list, i: int):
    """toks[i] == '(' -> (lista, índice siguiente). Tolera listas sin cerrar."""
    salida = []
    i += 1
    while i < len(toks):
        t = toks[i]
        if t == "(":
            sub, i = _lista(toks, i)
            salida.append(sub)
            continue
        if t == ")":
            return salida, i + 1
        salida.append(_valor(t))
        i += 1
    return salida, i


def mensajes(lineas) -> list[dict]:
    """Cada `n FETCH (...)` de la respuesta -> dict con claves en mayúsculas."""
    toks = tokens(lineas)
    salida = []
    i = 0
    while i + 2 < len(toks):
        a, b, c = toks[i], toks[i + 1], toks[i + 2]
        if (
            isinstance(a, tuple)
            and a[1].isdigit()
            and isinstance(b, tuple)
            and b[1].upper() == "FETCH"
            and c == "("
        ):
            datos, i = _lista(toks, i + 2)
            d = {}
            for k in range(0, len(datos) - 1, 2):
                if isinstance(datos[k], str):
                    d[datos[k].upper()] = datos[k + 1]
            salida.append(d)
            continue
        i += 1
    return salida


def parte_de_cuerpo(d: dict):
    """El primer `BODY[<sección>]<...>` del mensaje que no sea de cabeceras."""
    for k, v in d.items():
        if k.startswith("BODY[") and "HEADER" not in k:
            return v
    return None


def cabeceras(d: dict):
    for k, v in d.items():
        if k.startswith("BODY[HEADER"):
            return v
    return None
