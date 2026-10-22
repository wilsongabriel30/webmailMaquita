"""Estado de los certificados del correo entre pasadas del temporizador (/var/lib/maquita-dns/certificados.json).

Let's Encrypt limita las validaciones fallidas (5 por nombre y hora) y las emisiones por dominio. Un
linaje que falla no se vuelve a pedir en la pasada siguiente: espera 1 h, luego 2, 4, 8… hasta 7 días,
y la espera se reinicia en cuanto se emite. Aquí también queda el último aviso de configuración, para
que el panel lo muestre (el temporizador ya no queda «failed» por eso).
"""

import os
import time

from comun import guardar_json, leer_json

ESPERA_INICIAL = 3600
ESPERA_MAXIMA = 7 * 24 * 3600


def ruta():
    return os.getenv("MAQUITA_CERTIFICADOS_ESTADO", "/var/lib/maquita-dns/certificados.json")


def leer():
    try:
        datos = leer_json(ruta(), {})
    except (OSError, ValueError):
        datos = {}
    datos.setdefault("linajes", {})
    return datos


def _guardar(datos):
    guardar_json(ruta(), datos)


def espera(linaje, ahora=None):
    """Segundos que faltan para poder volver a pedir el linaje (0: se puede)."""
    ahora = ahora or time.time()
    proximo = leer()["linajes"].get(linaje, {}).get("proximo", 0)
    return max(0, int(proximo - ahora))


def fallo(linaje, error, ahora=None):
    ahora = ahora or time.time()
    datos = leer()
    l = datos["linajes"].setdefault(linaje, {})
    l["fallos"] = int(l.get("fallos", 0)) + 1
    pausa = min(ESPERA_INICIAL * 2 ** (l["fallos"] - 1), ESPERA_MAXIMA)
    l.update(proximo=int(ahora + pausa), error=str(error)[:500], ultimo_intento=int(ahora))
    _guardar(datos)
    return pausa


def exito(linaje, ahora=None):
    ahora = ahora or time.time()
    datos = leer()
    datos["linajes"][linaje] = {"fallos": 0, "proximo": 0, "ultimo_intento": int(ahora), "ultimo_exito": int(ahora)}
    _guardar(datos)


def de_linaje(linaje):
    return leer()["linajes"].get(linaje, {})


def anotar_aviso(texto, ahora=None):
    """Guarda (o borra, con texto vacío) el aviso de configuración de la última pasada."""
    datos = leer()
    anterior = datos.get("aviso")
    if not texto:
        if anterior is None:
            return
        datos.pop("aviso", None)
    else:
        if anterior and anterior.get("texto") == texto:
            return
        datos["aviso"] = {"texto": texto, "desde": int(ahora or time.time())}
    _guardar(datos)


def aviso():
    return leer().get("aviso")
