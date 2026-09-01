# -*- coding: utf-8 -*-
"""
Reconocer la tabla ANTES de que la pidan.
=========================================
«no le reconoce rápidamente lo que es la tabla, se demora bastante» — el
usuario, 29-jul-2026, y otra vez el 18-ago-2026.

Reconocer las tablas de una página cuesta entre 0,2 y 0,4 s. El editor lo pide
cuando el usuario activa la edición, y lo vuelve a pedir después de CADA cambio,
así que ese tiempo se paga una y otra vez con el usuario mirando.

Ya se adelantaba trabajo al abrir el documento, pero **no servía de nada**: el
adelanto se hacía con el contenido en bytes —cuya huella es el resumen SHA-1— y
el editor pregunta después por la sesión, cuya huella es «archivo-tamaño-fecha».
Dos huellas distintas para el mismo documento: lo recordado no se encontraba
nunca y se reconocía dos veces. Medido el 18-ago-2026: la primera consulta
seguía costando 0,405 s en vez de los 0,005 s de una ya recordada.

Aquí el adelanto se hace **con la misma referencia con la que se va a
preguntar** —el documento de la sesión— y por eso sí se aprovecha. Además:

· tras cada cambio se vuelve a adelantar la página tocada, que es justo la que
  el editor va a pedir en cuanto termine de recargar;
· el editor puede pedir el adelanto de la página que el usuario está mirando.

Nada de esto hace esperar a nadie: si el adelanto no llega a tiempo, la consulta
lo calcula como siempre.

Autoría: Equipo de Tecnología Maquita — 2026-08-18
"""

import logging
import threading

from . import cache_tablas, guardado_pdf, pool_pdf

logger = logging.getLogger(__name__)

# Cuánto se le da como mucho a un adelanto. Es trabajo regalado: si tarda más
# que esto, el usuario ya lo habrá pedido por su cuenta.
TIEMPO_MAXIMO = 60.0

# Qué páginas se adelantan al abrir el documento. Las primeras, que son las que
# se miran; el resto se adelantan al llegar a ellas.
PAGINAS_AL_ABRIR = (1, 2)

# Adelantos ya lanzados desde este proceso y todavía sin terminar. Evita que una
# ráfaga de cambios apile el mismo trabajo una y otra vez.
_EN_MARCHA = set()
_CANDADO = threading.Lock()


def _clave(referencia, numero_pagina):
    """La misma con la que `tablas_deteccion` recuerda lo reconocido."""
    return '%s-%d' % (guardado_pdf.huella_de(referencia), int(numero_pagina))


def _hace_falta(clave):
    """¿Merece la pena? No, si ya está recordado o ya se está calculando."""
    if cache_tablas.obtener(clave) is not None:
        return False
    with _CANDADO:
        if clave in _EN_MARCHA:
            return False
        _EN_MARCHA.add(clave)
    return True


def adelantar(referencia, paginas):
    """Reconoce en segundo plano las tablas de esas páginas. No espera a nada.

    `referencia` es lo mismo que se le pasaría a `detectar`: el contenido del
    PDF o un `PdfEnRuta` de la sesión. Debe ser **la misma forma** con la que
    luego se vaya a preguntar, o lo recordado no se encontrará.
    """
    if referencia is None:
        return
    for numero in paginas:
        try:
            numero = int(numero)
        except (TypeError, ValueError):
            continue
        if numero < 1:
            continue
        try:
            clave = _clave(referencia, numero)
        except OSError:
            # El documento ya no está (la sesión se cerró): no hay nada que
            # adelantar y tampoco es un fallo.
            return
        if not _hace_falta(clave):
            continue
        _lanzar(referencia, numero, clave)


def _lanzar(referencia, numero, clave):
    def trabajo():
        try:
            pool_pdf.ejecutar('detectar', referencia, numero,
                              tiempo_maximo=TIEMPO_MAXIMO)
        except Exception:
            logger.debug('adelanto de deteccion fallido', exc_info=True)
        finally:
            with _CANDADO:
                _EN_MARCHA.discard(clave)
    try:
        # El hilo solo sirve para no esperar aquí: el trabajo de verdad ocurre
        # en el grupo de procesos, así que este hilo se pasa la vida dormido y
        # no le quita el turno a nadie.
        threading.Thread(target=trabajo, daemon=True).start()
    except Exception:
        with _CANDADO:
            _EN_MARCHA.discard(clave)


def desde_sesion(ruta, paginas):
    """Adelanto sobre el documento de la sesión, tal como está AHORA.

    Se toma la huella en este momento —después de que el cambio se haya
    escrito—, que es la que tendrá la consulta que venga a continuación.
    """
    try:
        referencia = guardado_pdf.PdfEnRuta(ruta)
    except OSError:
        return
    adelantar(referencia, paginas)
