"""Ejecutar a la vez consultas lentas que no dependen unas de otras.

La comprobación previa a recuperar un correo consultaba los buzones de destino uno tras otro
(24 s con 8 destinatarios el 19/11/2026) y, al ser llamadas que bloquean, dejaba sin atender al
resto de personas de ese proceso mientras tanto. Aquí cada consulta va en un hilo aparte, con un
tope de simultáneas para no cargar el servidor de correo.
"""

import asyncio
from typing import Callable, Sequence, TypeVar

E = TypeVar("E")
R = TypeVar("R")

MAXIMO_SIMULTANEAS = 8


async def en_paralelo(
    funcion: Callable[[E], R],
    elementos: Sequence[E],
    maximo: int = MAXIMO_SIMULTANEAS,
) -> list[R]:
    """Aplica `funcion` a cada elemento, en hilos; devuelve los resultados en el mismo orden."""
    if not elementos:
        return []
    cupo = asyncio.Semaphore(max(1, maximo))

    async def uno(elemento: E) -> R:
        async with cupo:
            return await asyncio.to_thread(funcion, elemento)

    return list(await asyncio.gather(*(uno(e) for e in elementos)))
