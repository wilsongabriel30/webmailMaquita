# -*- coding: utf-8 -*-
"""Camino RÁPIDO de la consolidación ASC (11/09/2026).

    consolidar_rapido.py <ruta virtual de la matriz guardada> [--sandbox]

Cuando alguien edita una matriz territorial, quien tenga el consolidado
abierto debe verlo en segundos, no en los dos minutos y medio que tarda la
consolidación completa. Aquí se relee SOLO esa matriz, se sustituyen sus
fuentes en la caché de bloques (`bloques_cache`) y se señala a los editores
abiertos (`vivo.registrar_bloques`). No toca el archivo del consolidado en
disco: de eso sigue encargándose la consolidación completa, que va detrás.

Si todavía no hay caché de un consolidado (primera vez), no hace nada por él:
la completa la creará.
"""
import logging
import os
import sys
import time

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger('consolidar-rapido')

import consolidar_asc as c  # noqa: E402
import bloques_cache  # noqa: E402
import motor_consolidado as motor  # noqa: E402
import vivo  # noqa: E402


def main():
    argumentos = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not argumentos:
        log.error('uso: consolidar_rapido.py <ruta virtual de la matriz> [--sandbox]')
        return 2
    ruta_virtual = argumentos[0]
    if '--sandbox' in sys.argv:
        import sandbox
        sandbox.aplicar(c.__dict__)
    inicio = time.monotonic()
    if not ruta_virtual.startswith(c.BASE_VIRTUAL + '/'):
        log.error('la matriz no está bajo %s: %s', c.BASE_VIRTUAL, ruta_virtual)
        return 1
    fisica = os.path.join(c.BASE_FISICA, ruta_virtual[len(c.BASE_VIRTUAL) + 1:])
    if not os.path.isfile(fisica):
        log.error('no existe: %s', fisica)
        return 1

    lector = motor.LectorFuentes()
    tocados = 0
    try:
        for definicion in c.CONSOLIDADOS:
            cache = bloques_cache.cargar(c.ESTADO_DIR, definicion['archivo'])
            if not cache:
                continue
            cambiado = False
            for celda, fuentes in cache['bloques'].items():
                for fuente in fuentes:
                    if os.path.normpath(fuente['archivo']) == os.path.normpath(fisica):
                        fuente['filas'] = lector.leer_rango(fisica, fuente['hoja'], fuente['rango'])
                        cambiado = True
            if not cambiado:
                continue
            bloques_cache.guardar(c.ESTADO_DIR, definicion['archivo'], cache['hoja'],
                                  cache['bloques'])
            medidas = []
            for celda, fuentes in cache['bloques'].items():
                apilado = bloques_cache.apilar(fuentes)
                medidas.append((celda, len(apilado), len(apilado[0]) if apilado else 0))
            vivo.registrar_bloques(c.USUARIO, c.BASE_VIRTUAL + '/' + definicion['archivo'],
                                   cache['hoja'], medidas, invalidar=False)
            tocados += 1
            log.info('  %s: fuentes de %s releídas', os.path.basename(definicion['archivo']),
                     os.path.basename(fisica))
    finally:
        lector.cerrar()
    log.info('rápido: %d consolidado(s) señalados en %.1fs', tocados, time.monotonic() - inicio)
    return 0


if __name__ == '__main__':
    sys.exit(main())
