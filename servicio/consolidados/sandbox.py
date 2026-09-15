# -*- coding: utf-8 -*-
"""Caja de arena de los consolidados ASC (11/09/2026).

Wilson necesita probar «al límite» los consolidados y sus matrices sin tocar
la unidad de Planificación ASC. La caja de arena es una carpeta de su Drive
personal con COPIAS de los consolidados de 2026 y de todas sus matrices fuente:

    /PRUEBAS FORMULARIOS/ASC/<misma estructura que «Mi unidad de Google»>

`consolidar_asc.py --sandbox` hace exactamente lo mismo que en producción,
pero leyendo y escribiendo en esa carpeta (otro usuario, otra base, otro
estado, otro cerrojo). El enganche al guardar una matriz también lo dispara
cuando la matriz está dentro de la caja de arena. Nada de esto toca la unidad 12.
"""
import os

USUARIO = 14
BASE_VIRTUAL = '/PRUEBAS FORMULARIOS/ASC'
BASE_FISICA = '/mnt/almacen/14/archivos/PRUEBAS FORMULARIOS/ASC'
ESTADO_DIR = '/mnt/almacen/_sincronizacion-asc/estado-consolidados-sandbox'
CERROJO = '/var/lib/almacen-maquita/cerrojos/consolidados-asc-sandbox.lock'
REGISTRO = '/mnt/almacen/_sincronizacion-asc/registros/consolidacion-sandbox.log'
PREFIJO = BASE_VIRTUAL + '/'


# Consolidados que SOLO existen en la caja de arena: el «mini» es una copia del
# real (mismas fórmulas y misma tabla de configuración) con dos matrices y un
# rango corto, para validar el mecanismo en pequeño antes que en el grande.
CONSOLIDADOS_EXTRA = [
    {
        'archivo': 'Mini/Mini consolidado Ejec.xlsx',
        'hoja': 'ConsolidadoT',
        'fila_inicio': 5, 'fila_fin': 300,
        'bloques': [{'columna': 6, 'destino': 'G4', 'nombre': 'mini (A-AV)'}],
    },
]


def aplicar(espacio):
    """Redirige las constantes del consolidador a la caja de arena.
    `espacio` es `globals()` de `consolidar_asc`."""
    espacio['USUARIO'] = USUARIO
    espacio['CONSOLIDADOS'] = list(espacio['CONSOLIDADOS']) + CONSOLIDADOS_EXTRA
    espacio['BASE_VIRTUAL'] = BASE_VIRTUAL
    espacio['BASE_FISICA'] = BASE_FISICA
    espacio['ESTADO_DIR'] = ESTADO_DIR
    os.makedirs(ESTADO_DIR, exist_ok=True)


def es_ruta_sandbox(ruta):
    return bool(ruta) and ruta.startswith(PREFIJO)


def es_matriz_sandbox(ruta):
    """En la caja de arena, cualquier hoja de cálculo que no sea un consolidado
    cuenta como matriz fuente (así las copias «mini» también disparan)."""
    if not es_ruta_sandbox(ruta) or not ruta.lower().endswith(('.xlsx', '.xlsm')):
        return False
    nombre = ruta.rsplit('/', 1)[-1].lower()
    return 'consolidado' not in nombre and '/mapa de inversiones/' not in ruta.lower()
