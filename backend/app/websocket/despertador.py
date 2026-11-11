"""Despertar el sondeo de correo nuevo de una persona sin esperar la vuelta de 45 s (11/11/2026).

El webmail se entera de un correo nuevo preguntando al buzón cada 45 s; el correo ya estaba entregado
a los ≈5 s, pero la persona lo veía hasta un minuto después («en Zimbra llegaba en un parpadeo»).
Ahora el sondeo de cada persona espera un evento con tope de 45 s: cuando el servidor de correo avisa
de que hay un mensaje en camino para ella (`aviso_entrega.py` → canal Redis `ws:poke:<cuenta>`), el
sondeo corre enseguida. La entrega al buzón tarda algo más que el aviso, así que se despierta dos
veces: poco después y unos segundos más tarde.
"""

from __future__ import annotations

import asyncio

CANAL = "ws:poke:"
RETRASOS_S = (1.2, 5.0)
_eventos: dict[str, asyncio.Event] = {}


def _evento(usuario: str) -> asyncio.Event:
    ev = _eventos.get(usuario)
    if ev is None:
        ev = _eventos[usuario] = asyncio.Event()
    return ev


async def esperar(usuario: str, tope_s: float) -> bool:
    """Espera hasta `tope_s` o hasta que despierten a `usuario`. True si lo despertaron."""
    ev = _evento(usuario)
    try:
        await asyncio.wait_for(ev.wait(), timeout=tope_s)
    except asyncio.TimeoutError:
        return False
    ev.clear()
    return True


def despertar(usuario: str) -> None:
    """Programa las vueltas inmediatas del sondeo de `usuario` (si este proceso lo tiene)."""
    if usuario not in _eventos:
        return
    loop = asyncio.get_running_loop()
    for retraso in RETRASOS_S:
        loop.call_later(retraso, _poner, usuario)


def _poner(usuario: str) -> None:
    ev = _eventos.get(usuario)
    if ev is not None:
        ev.set()


def olvidar(usuario: str) -> None:
    _eventos.pop(usuario, None)
