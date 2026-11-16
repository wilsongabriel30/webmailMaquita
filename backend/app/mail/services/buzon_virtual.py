"""¿Tiene este servidor el buzón virtual «Virtual.Todo» (buscar en todas las carpetas)?

Informe de Andes (15/11/2026): en una instalación sin ese buzón, «Todas las carpetas» respondía
404 «Folder 'Virtual.Todo' not found» y, como la elección se guarda en la cuenta, quien la pulsaba
una vez se quedaba sin buscador. El buzón virtual es un ajuste aparte de Dovecot
(deploy/ajustes/84-dovecot-buzon-virtual.sh): no todas las instalaciones lo tienen.

Aquí se le pregunta al servidor de correo y la interfaz se entera por
`/api/mail/search/capacidades` (`todas_las_carpetas`): sin buzón virtual no ofrece ese ámbito, no
hace caso de la preferencia guardada y no lanza consultas a `Virtual.Todo`.

Cómo se pregunta: `LIST "" Virtual.Todo`. El espacio de nombres no se lista solo (`list = no`),
pero responde cuando se pide por su nombre, y no abre ningún buzón. Si LIST no lo muestra se
confirma con `STATUS`, que en un servidor sin buzón virtual responde NO en el acto. Comprobado con
Dovecot 2.4.1, con y sin el buzón. El resultado se recuerda en Redis: horas si existe (no va a
desaparecer) y pocos minutos si no (para que aparezca pronto tras aplicar el ajuste).
"""

from __future__ import annotations

import asyncio
import logging

from app.mail.services import tope_listado

log = logging.getLogger(__name__)

CARPETA_TODO = "Virtual.Todo"
TOPE_S = 8.0
RECORDAR_SI_S = 6 * 3600
RECORDAR_NO_S = 300
_NO_ES_BUZON = ("\\noselect", "\\nonexistent")


def _clave(usuario: str) -> str:
    return f"buzon_virtual:{(usuario or '').lower()}"


def _lo_lista(lineas) -> bool:
    for linea in lineas or []:
        if isinstance(linea, (bytes, bytearray)):
            linea = bytes(linea).decode("utf-8", errors="replace")
        texto = str(linea).strip()
        if not texto.startswith("(") or CARPETA_TODO.lower() not in texto.lower():
            continue
        marcas = texto[: texto.find(")")].lower()
        if not any(m in marcas for m in _NO_ES_BUZON):
            return True
    return False


async def _preguntar(imap) -> bool:
    resp = await imap.list('""', CARPETA_TODO)
    if getattr(resp, "result", "") == "OK" and _lo_lista(resp.lines):
        return True
    resp = await imap.status(CARPETA_TODO, "(UIDVALIDITY)")
    return getattr(resp, "result", "") == "OK"


async def existe(imap, redis=None, usuario: str = "") -> bool:
    """True si la cuenta puede buscar en `Virtual.Todo`. Ante cualquier duda, False.

    Nunca lanza: si el servidor no contesta a tiempo, la conexión se cierra (no vuelve al fondo
    de conexiones), se responde False y no se recuerda, para volver a preguntar la próxima vez.
    """
    clave = _clave(usuario)
    if redis is not None and usuario:
        try:
            guardado = await redis.get(clave)
            if guardado is not None:
                if isinstance(guardado, (bytes, bytearray)):
                    guardado = bytes(guardado).decode()
                return str(guardado) == "1"
        except Exception:
            pass
    try:
        hay = await asyncio.wait_for(_preguntar(imap), TOPE_S)
    except Exception as e:  # noqa: BLE001  (tiempo agotado o conexión caída)
        tope_listado.cortar(imap)
        log.warning("buzon_virtual: no se pudo comprobar (%s)", type(e).__name__)
        return False
    if redis is not None and usuario:
        try:
            await redis.set(
                clave, "1" if hay else "0", ex=RECORDAR_SI_S if hay else RECORDAR_NO_S
            )
        except Exception:
            pass
    return hay
