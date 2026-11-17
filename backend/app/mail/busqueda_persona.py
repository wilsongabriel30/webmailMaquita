"""Buscar la correspondencia con UNA persona, distinguiendo lo directo de las copias (17/11/2026).

Pedido de los usuarios: «quiero ver solo lo que Mariana me envió o lo que yo le envié, no lo que
recibí en copia ni aquello en lo que ella iba en copia». Con `de:` y `para:` no se puede decir:
`de:mariana` trae también lo que ella envió a otros con copia a uno, y `para:mariana` no mira quién
lo envió.

Operadores (el panel «Buscar un correo» los compone; también se pueden escribir en la caja):

  con:x        todo donde aparece x: lo envió, se le envió o iba en copia
  directo:x    solo lo directo, en los dos sentidos: x me lo envió a mí, o yo se lo envié a x
  meenvio:x    solo lo que x me envió a mí (yo en «Para», no en copia)
  leenvie:x    solo lo que yo le envié a x (x en «Para», no en copia)

«A mí» y «yo» son las direcciones de la cuenta que busca: la suya y sus alias personales (las
otras direcciones que entregan solo en su buzón; las listas no cuentan). Si no se conocen, los
tres últimos se quedan en remitente y destinatario, sin la condición de la otra parte.

La persona se puede escribir con varias palabras («Mariana López»): tienen que estar todas en
el mismo campo, en cualquier orden, así que también encuentra «López Paredes, Mariana».

Todo va por cabecera, que es lo que el servidor tiene indexado: no hay que abrir ningún mensaje.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from app.mail import busqueda_palabras


def _campo(
    campo: str,
    valores: Iterable[str],
    comillas: Callable[[str], str],
    con_tildes: bool = True,
) -> str:
    """`campo` con cualquiera de `valores`, como un solo criterio.

    Con `con_tildes` se añaden las variantes acentuadas («barbara» encuentra a «Bárbara»), igual
    que en `de:` y `para:`. Las direcciones propias van tal cual: son correos, no nombres.
    """
    formas: list[str] = []
    for valor in valores:
        candidatas = busqueda_palabras.variantes(valor) if con_tildes else [valor]
        for forma in candidatas:
            if forma and forma not in formas:
                formas.append(forma)
    partes = [f"{campo} {comillas(f)}" for f in formas]
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0]
    return "(" + " ".join(["OR"] * (len(partes) - 1) + partes) + ")"


def _y(*criterios: str) -> str:
    return "(" + " ".join(c for c in criterios if c) + ")"


def _persona(campo: str, valor: str, comillas: Callable[[str], str]) -> str:
    """La persona en `campo`: todas sus palabras, en cualquier orden."""
    palabras = [_campo(campo, (p,), comillas) for p in valor.split()]
    palabras = [p for p in palabras if p]
    if len(palabras) <= 1:
        return palabras[0] if palabras else ""
    return _y(*palabras)


def con(valor: str, comillas: Callable[[str], str]) -> list[str]:
    """Todo donde aparece la persona: remitente, destinatario o copia."""
    return [
        "OR",
        _persona("FROM", valor, comillas),
        "OR",
        _persona("TO", valor, comillas),
        _persona("CC", valor, comillas),
    ]


def me_envio(
    valor: str, mias: Iterable[str], comillas: Callable[[str], str]
) -> list[str]:
    """La persona lo envió y yo estoy en «Para»."""
    return [_y(_persona("FROM", valor, comillas), _campo("TO", mias, comillas, False))]


def le_envie(
    valor: str, mias: Iterable[str], comillas: Callable[[str], str]
) -> list[str]:
    """Yo lo envié y la persona está en «Para»."""
    return [_y(_campo("FROM", mias, comillas, False), _persona("TO", valor, comillas))]


def directo(
    valor: str, mias: Iterable[str], comillas: Callable[[str], str]
) -> list[str]:
    """Lo directo en los dos sentidos; nada de lo que uno de los dos recibió solo en copia."""
    mias = tuple(mias)
    return ["OR", *me_envio(valor, mias, comillas), *le_envie(valor, mias, comillas)]


OPERADORES = {
    "with:": lambda v, mias, q: con(v, q),
    "direct:": directo,
    "sentme:": me_envio,
    "isent:": le_envie,
}


def usa_operador(consulta: str) -> bool:
    """¿La consulta necesita saber quién busca? (para no consultar los alias en cada búsqueda)."""
    bajo = (consulta or "").lower()
    return any(
        op in bajo
        for op in ("directo:", "meenvio:", "meenvió:", "leenvie:", "leenvié:")
        + ("direct:", "sentme:", "isent:")
    )


def criterio(
    token: str, mias: Iterable[str], comillas: Callable[[str], str]
) -> list[str] | None:
    """Los criterios IMAP de `token` si es uno de estos operadores (ya en su forma canónica)."""
    bajo = token.lower()
    for prefijo, hacer in OPERADORES.items():
        if bajo.startswith(prefijo):
            valor = token[len(prefijo) :].strip().strip(chr(34))
            return hacer(valor, tuple(mias), comillas) if valor else []
    return None
