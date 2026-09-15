# -*- coding: utf-8 -*-
"""Dispara la consolidación cuando alguien guarda una matriz territorial.

Hasta el corte del 28/09/2026 las matrices llegan de Google y la consolidación
la dispara el cron de sincronización. Después del corte las matrices se editan
aquí, así que hace falta este enganche: al guardar una matriz desde el editor,
el consolidado se rehace sin esperar a nadie.

Regla de la casa: **nada pesado dentro de gunicorn**. Consolidar lleva minutos y
abre decenas de libros, así que aquí solo se lanza un proceso aparte y se
devuelve el control de inmediato. `flock` evita que se pise con el cron o con
otro guardado casi simultáneo.
"""
import logging
import os
import subprocess

log = logging.getLogger(__name__)

DIRECTORIO = os.path.dirname(os.path.abspath(__file__))
# Los módulos hermanos (sandbox, …) también deben importarse desde gunicorn,
# donde este archivo entra como consolidados.enganche (11/09/2026).
import sys as _sys
if DIRECTORIO not in _sys.path:
    _sys.path.insert(0, DIRECTORIO)
GUION = os.path.join(DIRECTORIO, 'consolidar_asc.py')
GUION_RAPIDO = os.path.join(DIRECTORIO, 'consolidar_rapido.py')
CERROJO_RAPIDO = '/var/lib/almacen-maquita/cerrojos/consolidados-asc-rapido.lock'
EQUIVALENCIAS = os.path.join(DIRECTORIO, 'equivalencias-google.tsv')
PYTHON = '/home/sistemas/Maquita/venv/bin/python'
# (11/09/2026) Fuera de /var/lock: con fs.protected_regular=2, root no puede
# abrir un archivo creado por `sistemas` en un directorio con sticky bit, y el
# cron de consolidación llevaba fallando desde el 09/09 («Permiso denegado»).
CERROJO = '/var/lib/almacen-maquita/cerrojos/consolidados-asc.lock'
REGISTRO = '/mnt/almacen/_sincronizacion-asc/registros/consolidacion-al-guardar.log'

PREFIJO_UNIDAD = '/unidades/12/'

_matrices = None


def matrices_fuente():
    """Nombres de las matrices que alimentan algún consolidado (sin extensión).

    Se toman de la tabla de equivalencias de la migración. Si mañana suman una
    matriz que no esté ahí, el enganche no saltará para ella, pero el cron de
    consolidación la recogerá igual: esto acelera, no es la única vía.
    """
    global _matrices
    if _matrices is None:
        nombres = set()
        try:
            with open(EQUIVALENCIAS, encoding='utf-8') as fichero:
                next(fichero, None)
                for linea in fichero:
                    columnas = linea.rstrip('\n').split('\t')
                    if len(columnas) >= 9 and columnas[8].strip():
                        nombres.add(os.path.splitext(
                            os.path.basename(columnas[8].strip()))[0])
        except OSError as excepcion:
            log.warning('consolidados: no se pudo leer %s: %s', EQUIVALENCIAS, excepcion)
        _matrices = nombres
    return _matrices


def _en_sandbox(ruta):
    try:
        import sandbox
        return sandbox.es_ruta_sandbox(ruta)
    except Exception:
        return False


def es_matriz_fuente(ruta):
    # También las copias de la caja de arena de pruebas (11/09/2026).
    if not ruta or not (ruta.startswith(PREFIJO_UNIDAD) or _en_sandbox(ruta)):
        return False
    if not ruta.lower().endswith(('.xlsx', '.xlsm')):
        return False
    if _en_sandbox(ruta):
        import sandbox
        return sandbox.es_matriz_sandbox(ruta)
    return os.path.splitext(os.path.basename(ruta))[0] in matrices_fuente()


def al_guardar(ruta):
    """Lanza la consolidación en segundo plano si `ruta` es una matriz fuente.

    Devuelve True si la lanzó. Nunca lanza excepción: el guardado del usuario
    no puede romperse por esto.
    """
    try:
        if not es_matriz_fuente(ruta):
            return False
        registro, cerrojo, extra = REGISTRO, CERROJO, []
        if _en_sandbox(ruta):
            import sandbox
            registro, cerrojo, extra = sandbox.REGISTRO, sandbox.CERROJO, ['--sandbox']
        os.makedirs(os.path.dirname(registro), exist_ok=True)
        # Camino rápido (segundos): relee solo esta matriz y avisa a los
        # consolidados abiertos. Cerrojo SIN -n: si llegan dos guardados
        # seguidos, el segundo espera; no se pierde ninguno (11/09/2026).
        with open(registro, 'a', encoding='utf-8') as salida:
            subprocess.Popen(
                ['flock', CERROJO_RAPIDO, PYTHON, GUION_RAPIDO, ruta] + extra,
                stdout=salida, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True)
        with open(registro, 'a', encoding='utf-8') as salida:
            subprocess.Popen(
                ['flock', '-n', cerrojo, PYTHON, GUION] + extra,
                stdout=salida, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True)
        log.info('consolidados: lanzada consolidación por guardado de %s', ruta)
        return True
    except Exception as excepcion:
        log.warning('consolidados: no se pudo lanzar por %s: %s', ruta, excepcion)
        return False
