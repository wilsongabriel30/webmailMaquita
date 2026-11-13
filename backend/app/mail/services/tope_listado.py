"""Tope de tiempo del listado de correos, y corte si quien lo pidió ya no espera (13/11/2026).

Una búsqueda que se alarga no puede quedarse viva en el servidor de correo. Caso real del
13/11/2026: una búsqueda en «todas las carpetas» estuvo cinco minutos leyendo buzones (el índice
de texto de alguna carpeta no estaba al día y Dovecot lo completa al buscar) cuando el navegador
ya había dejado de esperarla; hubo que matar el proceso a mano.

Aquí el listado corre vigilado. Se corta —y la conexión IMAP se cierra en el acto, sin volver al
fondo de conexiones— en tres casos: pasa del tope, el navegador cerró la petición o el servidor
web la cancela. Límite conocido: si Dovecot está en mitad de una orden larga, se entera del cierre
cuando termina esa orden; lo que se garantiza es que el webmail no lo espera ni le manda más.
"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import HTTPException

log = logging.getLogger(__name__)

TOPE_LISTA_S = 45.0  # el navegador espera 30 s; nginx, 60
CADA_S = 1.0  # cada cuánto se mira si el navegador sigue ahí


def cortar(imap) -> None:
    """Cierra la conexión IMAP ahora y la marca para que no vuelva al fondo de conexiones."""
    setattr(imap, "conexion_sucia", True)
    try:
        imap.protocol.transport.close()
    except Exception:
        pass


async def _se_fue(request) -> bool:
    try:
        return bool(await asyncio.wait_for(request.is_disconnected(), 0.5))
    except Exception:
        return False


async def ejecutar(request, imap, corrutina, tope: float | None = None):
    """Devuelve el resultado de `corrutina` (un listado sobre `imap`) o corta la conexión.

    Las excepciones del listado pasan tal cual. Al agotar el tope: 504. Si el navegador cerró la
    petición: 499 (nadie lo lee; queda en el registro).
    """
    tope = TOPE_LISTA_S if tope is None else tope
    t0 = time.monotonic()
    tarea = asyncio.ensure_future(corrutina)
    try:
        while True:
            hechas, _ = await asyncio.wait({tarea}, timeout=CADA_S)
            if hechas:
                return tarea.result()
            pasado = time.monotonic() - t0
            if pasado >= tope:
                motivo, estado = f"pasó de {tope:.0f} s", 504
            elif await _se_fue(request):
                motivo, estado = (
                    f"el navegador cerró la petición a los {pasado:.0f} s",
                    499,
                )
            else:
                continue
            log.warning(
                "tope_listado: listado cortado (%s); conexión IMAP cerrada", motivo
            )
            raise HTTPException(
                status_code=estado,
                detail="La búsqueda tardó demasiado y se detuvo. Inténtelo de nuevo en un momento.",
            )
    finally:
        if not tarea.done():
            # Tope, navegador ausente o petición cancelada: nada debe seguir usando esta conexión.
            tarea.cancel()
            cortar(imap)
