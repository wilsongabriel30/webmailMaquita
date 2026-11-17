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

«A mí» y «yo» son las direcciones de la cuenta que busca. Si no se conocen, los tres últimos se
quedan en remitente y destinatario, sin la condición de la otra parte. Todo va por cabecera, que
es lo que el servidor tiene indexado: no hay que abrir ningún mensaje.
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


def con(valor: str, comillas: Callable[[str], str]) -> list[str]:
    """Todo donde aparece la persona: remitente, destinatario o copia."""
    v = (valor,)
    return [
        "OR",
        _campo("FROM", v, comillas),
        "OR",
        _campo("TO", v, comillas),
        _campo("CC", v, comillas),
    ]


def me_envio(
    valor: str, mias: Iterable[str], comillas: Callable[[str], str]
) -> list[str]:
    """La persona lo envió y yo estoy en «Para»."""
    return [_y(_campo("FROM", (valor,), comillas), _campo("TO", mias, comillas, False))]


def le_envie(
    valor: str, mias: Iterable[str], comillas: Callable[[str], str]
) -> list[str]:
    """Yo lo envié y la persona está en «Para»."""
    return [_y(_campo("FROM", mias, comillas, False), _campo("TO", (valor,), comillas))]


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
