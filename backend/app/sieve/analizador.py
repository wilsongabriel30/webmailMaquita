"""Relee el script Sieve «webmail» y recupera las reglas y la respuesta automática.

Acepta lo que genera `generador.py` hoy (varias condiciones con allof/anyof, `not`, `body`,
`size`, `exists`, `:regex`, listas de encabezados, varias acciones, `:copy`, regla desactivada
con `allof (false, …)`) y lo que generaron las versiones anteriores: `header` y `address` en
la condición, `fileinto` con o sin `:create`, `setflag` y `addflag`, con o sin `stop;`, y
cadenas con escapes (`\\"`, `\\\\`). Un script antiguo con `header :is "From"` se relee como
«De es exactamente» y, al guardarse de nuevo, el generador lo escribe ya con `address`.

El bloque de cada regla se lee con un pequeño tokenizador (cadenas, listas, paréntesis,
llaves): una expresión regular no bastaba con comas dentro de las cadenas y tests anidados.
Lo que no se entiende se omite (la regla no se relee; `comprobar_relectura` lo detecta antes
de guardar).
"""

import math
import re
from dataclasses import dataclass, field
from typing import Optional, Union

from app.sieve.escapado import CADENA, desescapar
from app.sieve.modelos import (
    FilterAction,
    FilterCondition,
    FilterRule,
    VacationSettings,
    bandera_canonica,
)

_VACACIONES = re.compile(
    r"vacation\s+:days\s+\d+\s+:subject\s+" + CADENA + r"\s+" + CADENA + r"\s*;",
    re.DOTALL,
)
_DESDE = re.compile(r'currentdate\s+:value\s+"ge"\s+"date"\s+' + CADENA)
_HASTA = re.compile(r'currentdate\s+:value\s+"le"\s+"date"\s+' + CADENA)

_MARCA_REGLA = re.compile(r"^#\s*filter\[\d+\]:[ \t]*(.*?)[ \t]*$", re.MULTILINE)

_CAMPO_POR_ENCABEZADOS = {
    ("from",): "from",
    ("to",): "to",
    ("cc",): "cc",
    ("to", "cc"): "recipients",
    ("cc", "to"): "recipients",
    ("subject",): "subject",
    ("list-id",): "list",
}
_OPERADOR = {
    ":contains": "contains",
    ":is": "is",
    ":matches": "matches",
    ":regex": "regex",
}


# ── Tokenizador ───────────────────────────────────────────────────────────────


@dataclass
class _Tok:
    tipo: str  # str, word, tag, [, ], (, ), {, }, ",", ";"
    valor: str = ""


_TOKEN = re.compile(
    r"\s+|#[^\n]*"  # espacios y comentarios
    r"|(?P<str>" + CADENA + r")"
    r"|(?P<tag>:[A-Za-z0-9_]+)"
    r"|(?P<word>[A-Za-z0-9_\\.]+)"
    r"|(?P<sym>[\[\](){},;])",
    re.DOTALL,
)


def _tokenizar(texto: str) -> list[_Tok]:
    toks: list[_Tok] = []
    pos = 0
    while pos < len(texto):
        m = _TOKEN.match(texto, pos)
        if not m:
            raise ValueError(
                f"carácter inesperado en el script: {texto[pos:pos + 10]!r}"
            )
        pos = m.end()
        if m.group("str") is not None:
            toks.append(_Tok("str", desescapar(m.group("str")[1:-1])))
        elif m.group("tag"):
            toks.append(_Tok("tag", m.group("tag").lower()))
        elif m.group("word"):
            toks.append(_Tok("word", m.group("word")))
        elif m.group("sym"):
            toks.append(_Tok(m.group("sym")))
    return toks


# ── Árbol de tests ────────────────────────────────────────────────────────────


@dataclass
class _Atomo:
    nombre: str
    tags: list[str] = field(default_factory=list)
    args: list[Union[str, list[str]]] = field(default_factory=list)
    negado: bool = False


@dataclass
class _Grupo:
    tipo: str  # allof | anyof
    hijos: list = field(default_factory=list)


_Test = Union[_Atomo, _Grupo]


class _Lector:
    def __init__(self, toks: list[_Tok]):
        self.toks = toks
        self.i = 0

    def ver(self) -> Optional[_Tok]:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def tomar(self, tipo: Optional[str] = None) -> _Tok:
        tok = self.ver()
        if tok is None or (tipo and tok.tipo != tipo):
            raise ValueError(f"se esperaba {tipo or 'algo'} y hay {tok}")
        self.i += 1
        return tok

    def lista_o_cadena(self) -> Union[str, list[str]]:
        tok = self.ver()
        if tok is not None and tok.tipo == "str":
            return self.tomar("str").valor
        self.tomar("[")
        valores: list[str] = []
        while True:
            valores.append(self.tomar("str").valor)
            if self.ver() and self.ver().tipo == ",":
                self.tomar(",")
                continue
            self.tomar("]")
            return valores

    def test(self) -> _Test:
        tok = self.tomar("word")
        palabra = tok.valor.lower()
        if palabra == "not":
            interior = self.test()
            if isinstance(interior, _Atomo):
                interior.negado = not interior.negado
                return interior
            raise ValueError("«not» sobre un grupo no se admite")
        if palabra in ("allof", "anyof"):
            self.tomar("(")
            grupo = _Grupo(palabra)
            while True:
                grupo.hijos.append(self.test())
                if self.ver() and self.ver().tipo == ",":
                    self.tomar(",")
                    continue
                self.tomar(")")
                return grupo
        atomo = _Atomo(palabra)
        while True:
            sig = self.ver()
            if sig is None or sig.tipo in (",", ")", "{"):
                return atomo
            if sig.tipo == "tag":
                atomo.tags.append(self.tomar("tag").valor)
                # `:comparator "i;ascii-casemap"`: el argumento acompaña a la etiqueta.
                if atomo.tags[-1] == ":comparator":
                    atomo.args.append(self.tomar("str").valor)
                    atomo.args.pop()
            elif sig.tipo == "word":
                atomo.args.append(self.tomar("word").valor)
            else:
                atomo.args.append(self.lista_o_cadena())

    def comandos(self) -> list[list[_Tok]]:
        """Los comandos del bloque `{ … }` (cada uno como lista de tokens, sin el `;`)."""
        self.tomar("{")
        comandos: list[list[_Tok]] = []
        actual: list[_Tok] = []
        while True:
            tok = self.tomar()
            if tok.tipo == "}":
                return comandos
            if tok.tipo == ";":
                if actual:
                    comandos.append(actual)
                actual = []
            else:
                actual.append(tok)


# ── De árbol a condiciones y acciones ─────────────────────────────────────────


def _kilobytes(texto: str) -> int:
    m = re.fullmatch(r"(\d+)([KkMmGg]?)", texto)
    if not m:
        raise ValueError(f"tamaño no entendido: {texto}")
    n = int(m.group(1))
    unidad = m.group(2).upper()
    if unidad == "K":
        return n
    if unidad == "M":
        return n * 1024
    if unidad == "G":
        return n * 1024 * 1024
    return max(1, math.ceil(n / 1024))


def _campo(encabezados: Union[str, list[str]]) -> tuple[str, Optional[str]]:
    lista = [encabezados] if isinstance(encabezados, str) else list(encabezados)
    clave = tuple(h.lower() for h in lista)
    campo = _CAMPO_POR_ENCABEZADOS.get(clave)
    if campo:
        return campo, None
    if len(lista) == 1:
        return "header", lista[0]
    raise ValueError(f"lista de encabezados no admitida: {lista}")


def _condicion(atomo: _Atomo) -> FilterCondition:
    nombre = atomo.nombre
    prefijo = "not_" if atomo.negado else ""
    if nombre == "size":
        op = "over" if ":over" in atomo.tags else "under"
        if atomo.negado:
            # `not size :over` equivale a `size :under` (y viceversa).
            op = "under" if op == "over" else "over"
        return FilterCondition(
            field="size", operator=op, value=str(_kilobytes(str(atomo.args[0])))
        )
    comparador = next((t for t in atomo.tags if t in _OPERADOR), ":contains")
    operador = _OPERADOR[comparador]
    if nombre == "body":
        return FilterCondition(
            field="body", operator=prefijo + operador, value=str(atomo.args[-1])
        )
    if nombre == "exists":
        campo, encabezado = _campo(atomo.args[0])
        return FilterCondition(
            field=campo, operator=prefijo + "exists", header=encabezado
        )
    if nombre in ("header", "address"):
        campo, encabezado = _campo(atomo.args[0])
        return FilterCondition(
            field=campo,
            operator=prefijo + operador,
            value=str(atomo.args[1]),
            header=encabezado,
        )
    raise ValueError(f"test no admitido: {nombre}")


def _accion(toks: list[_Tok]) -> Optional[FilterAction]:
    nombre = toks[0].valor.lower()
    tags = {t.valor for t in toks[1:] if t.tipo == "tag"}
    cadenas = [t.valor for t in toks[1:] if t.tipo == "str"]
    if nombre == "fileinto":
        tipo = "copy" if ":copy" in tags else "move"
        return FilterAction(type=tipo, value=cadenas[-1] if cadenas else "INBOX")
    if nombre in ("addflag", "setflag"):
        bandera = bandera_canonica(cadenas[-1] if cadenas else None)
        if bandera.lower() == "\\seen":
            return FilterAction(type="read")
        return FilterAction(type="flag", value=bandera)
    if nombre == "discard":
        return FilterAction(type="delete")
    if nombre == "redirect":
        tipo = "forward_copy" if ":copy" in tags else "forward"
        return FilterAction(type=tipo, value=cadenas[-1] if cadenas else "")
    return None  # stop, keep u otros: no son acciones de la regla


def _regla(nombre: str, bloque: str) -> Optional[FilterRule]:
    lector = _Lector(_tokenizar(bloque))
    if lector.tomar("word").valor.lower() != "if":
        return None
    arbol = lector.test()
    comandos = lector.comandos()

    enabled = True
    if (
        isinstance(arbol, _Grupo)
        and arbol.tipo == "allof"
        and arbol.hijos
        and isinstance(arbol.hijos[0], _Atomo)
        and arbol.hijos[0].nombre == "false"
    ):
        enabled = False
        resto = arbol.hijos[1:]
        arbol = resto[0] if len(resto) == 1 else _Grupo("allof", resto)

    if isinstance(arbol, _Grupo):
        match = arbol.tipo
        atomos = arbol.hijos
    else:
        match = "allof"
        atomos = [arbol]
    if not all(isinstance(a, _Atomo) for a in atomos):
        return None  # grupos anidados: no los genera el webmail
    conditions = [_condicion(a) for a in atomos]

    actions: list[FilterAction] = []
    stop = False
    for cmd in comandos:
        if cmd[0].tipo != "word":
            continue
        if cmd[0].valor.lower() == "stop":
            stop = True
            continue
        accion = _accion(cmd)
        if accion is not None:
            actions.append(accion)
    if not actions:
        return None
    return FilterRule(
        name=nombre.strip(),
        match=match,
        conditions=conditions,
        actions=actions,
        stop=stop,
        enabled=enabled,
    )


# ── API pública ───────────────────────────────────────────────────────────────


def parse_vacation_from_script(script: str) -> VacationSettings:
    """La respuesta automática del script (apagada si no hay orden `vacation`)."""
    if not script:
        return VacationSettings(enabled=False)
    m = _VACACIONES.search(script)
    if not m:
        return VacationSettings(enabled=False)
    desde = _DESDE.search(script)
    hasta = _HASTA.search(script)
    return VacationSettings(
        enabled=True,
        subject=desescapar(m.group(1)),
        body=desescapar(m.group(2)),
        start_date=desescapar(desde.group(1)) if desde else None,
        end_date=desescapar(hasta.group(1)) if hasta else None,
    )


def parse_filters_from_script(script: str) -> list[FilterRule]:
    """Las reglas de la persona, en el orden del script. Lo que no se entiende se omite."""
    if not script:
        return []
    marcas = list(_MARCA_REGLA.finditer(script))
    reglas: list[FilterRule] = []
    for n, m in enumerate(marcas):
        fin = marcas[n + 1].start() if n + 1 < len(marcas) else len(script)
        bloque = script[m.end() : fin]
        try:
            regla = _regla(desescapar(m.group(1)), bloque)
        except (ValueError, IndexError):
            regla = None
        if regla is not None:
            reglas.append(regla)
    return reglas
