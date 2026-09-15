#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rehace los consolidados de Planificación ASC dentro del Drive Maquita.

En Google, «Mapa general de inversiones 2026» y «Mapa general Ejec. Técnica
2026» se alimentaban de las matrices territoriales con
`QUERY({IMPORTRANGE(...); IMPORTRANGE(...)})`. Ni OnlyOffice ni Excel tienen
`QUERY`, así que al salir de Google esos consolidados quedaban CONGELADOS.

Este proceso les devuelve la capacidad: lee la tabla de configuración que la
propia hoja lleva dentro (mismas columnas que usaba la fórmula), apila los
rangos de cada matriz y escribe el resultado como valores en el consolidado.

Uso:
    consolidar_asc.py            # consolida solo si alguna matriz cambió
    consolidar_asc.py --forzar   # consolida siempre
    consolidar_asc.py --prueba   # informa qué haría, no escribe nada
"""
import csv
import io
import json
import logging
import os
import re
import sys
import tempfile

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl  # noqa: E402
from openpyxl.utils.cell import coordinate_to_tuple  # noqa: E402

import nucleo_archivos as nucleo  # noqa: E402
from seguridad_rutas import ruta_fisica  # noqa: E402

import config_consolidado as cfg  # noqa: E402
import motor_consolidado as motor  # noqa: E402
from inyectar_valores import completar  # noqa: E402
import vivo  # noqa: E402  (consolidado abierto en el editor: en vivo, 11/09/2026)

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger('consolidar-asc')

UNIDAD = 12
USUARIO = 14                     # Wilson Argüello, manager de la unidad
BASE_VIRTUAL = f'/unidades/{UNIDAD}/Mi unidad de Google'
BASE_FISICA = f'/mnt/almacen/_unidades/{UNIDAD}/archivos/Mi unidad de Google'

CONSOLIDADOS = [
    {
        'archivo': 'Mapa de inversiones/Mapa general de inversiones 2026.xlsx',
        'hoja': 'ConsolidadoP',
        # El final de la tabla NO se fija: se detecta. Cuando el equipo añade un
        # proyecto (ya pasó: se sumó E11 y R14 bajó de la fila 39 a la 40), el
        # consolidado lo toma solo, igual que hacía Google.
        'fila_inicio': 5, 'fila_fin': 300,
        'bloques': [
            {'columna': cfg.COL_RANGO1, 'destino': 'H4', 'nombre': 'presupuesto (A-I)'},
            {'columna': cfg.COL_RANGO2, 'destino': 'U4', 'nombre': 'meses'},
        ],
    },
    {
        'archivo': 'Mapa de inversiones/Mapa general Ejec. Técnica 2026.xlsx',
        'hoja': 'ConsolidadoT',
        'fila_inicio': 5, 'fila_fin': 300,
        'bloques': [
            {'columna': cfg.COL_RANGO1, 'destino': 'G4', 'nombre': 'ejecución técnica (A-AV)'},
        ],
    },
    # Año cerrado, se mantiene vivo a pedido de Wilson (09/09).
    {
        'archivo': 'Mapa de inversiones/Mapa general de inversiones 2025.xlsx',
        'hoja': 'ConsolidadoP',
        'fila_inicio': 5, 'fila_fin': 300,
        'bloques': [
            {'columna': cfg.COL_RANGO1, 'destino': 'H4', 'nombre': 'presupuesto (A-I)'},
            {'columna': cfg.COL_RANGO2, 'destino': 'U4', 'nombre': 'meses'},
        ],
    },
    # Sus fuentes vienen como URL de Google, no como nombre: se resuelven con
    # `equivalencias-google.tsv`.
    {
        'archivo': 'Mapa de inversiones/Respaldo mapa inversiones.xlsx',
        'hoja': 'ConsolidadoP',
        'fila_inicio': 5, 'fila_fin': 300,
        'bloques': [
            {'columna': cfg.COL_RANGO1, 'destino': 'H4', 'nombre': 'presupuesto (A-I)'},
            {'columna': cfg.COL_RANGO2, 'destino': 'U4', 'nombre': 'meses'},
        ],
    },
]


from rutas_estado import ESTADO_DIR  # noqa: E402  (compartido con la API en vivo)
import bloques_cache  # noqa: E402  (caché por fuente para el camino rápido, 11/09/2026)

# Equivalencias id de Google → archivo, levantadas en la migración del 06/08.
# «Respaldo mapa inversiones» no guarda el nombre del archivo en la columna LINK
# sino la URL de Google, así que sus fuentes se resuelven por este mapa.
MAPA_IDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'equivalencias-google.tsv')
_RE_ID_GOOGLE = re.compile(r'/d/([A-Za-z0-9_-]+)')


def mapa_ids_google():
    """id de Google → nombre de archivo sin extensión."""
    equivalencias = {}
    try:
        with open(MAPA_IDS, encoding='utf-8') as fichero:
            for fila in csv.DictReader(fichero, delimiter='\t'):
                identificador = (fila.get('id_fuente') or '').strip()
                archivo = (fila.get('archivo_fuente') or '').strip()
                if identificador and archivo:
                    equivalencias[identificador] = os.path.splitext(
                        os.path.basename(archivo))[0]
    except OSError:
        log.warning('no se pudo leer %s: las fuentes por URL no se resolverán',
                    MAPA_IDS)
    return equivalencias


def resolver_fuente(fuente, indice, equivalencias):
    """Ruta física de la matriz de una fuente, sea por nombre o por URL."""
    referencia = fuente.archivo
    coincidencia = _RE_ID_GOOGLE.search(referencia)
    if coincidencia:
        referencia = equivalencias.get(coincidencia.group(1), '')
    return indice.get(referencia)


def _ruta_estado(definicion):
    nombre = os.path.basename(definicion['archivo']).replace('/', '_') + '.json'
    return os.path.join(ESTADO_DIR, nombre)


def leer_estado(definicion):
    try:
        with open(_ruta_estado(definicion), encoding='utf-8') as fichero:
            return json.load(fichero)
    except (OSError, ValueError):
        return {}


def guardar_estado(definicion, destino_mtime, fuentes_mtime):
    os.makedirs(ESTADO_DIR, exist_ok=True)
    with open(_ruta_estado(definicion), 'w', encoding='utf-8') as fichero:
        json.dump({'destino_mtime': destino_mtime, 'fuentes_mtime': fuentes_mtime},
                  fichero)


def indice_de_archivos():
    """nombre de archivo (sin extensión) → ruta física, dentro de la unidad."""
    indice = {}
    for carpeta, _, archivos in os.walk(BASE_FISICA):
        for nombre in archivos:
            if nombre.lower().endswith(('.xlsx', '.xlsm')):
                indice.setdefault(os.path.splitext(nombre)[0], os.path.join(carpeta, nombre))
    return indice


def procesar(definicion, indice, equivalencias, forzar=False, prueba=False):
    ruta_destino = os.path.join(BASE_FISICA, definicion['archivo'])
    titulo = os.path.basename(definicion['archivo'])
    if not os.path.isfile(ruta_destino):
        log.error('  NO EXISTE el consolidado: %s', definicion['archivo'])
        return False

    log.info('\n== %s · hoja %s ==', titulo, definicion['hoja'])
    # Sin `read_only`: la tabla de configuración se lee una sola vez y tiene que
    # salir exacta. En modo read_only openpyxl puede desalinear las filas.
    libro_cfg = openpyxl.load_workbook(ruta_destino, data_only=True)
    try:
        hoja_cfg = libro_cfg[definicion['hoja']]
        planes = []
        for bloque in definicion['bloques']:
            fuentes = cfg.leer_fuentes(hoja_cfg, definicion['fila_inicio'],
                                       definicion['fila_fin'], bloque['columna'])
            planes.append((bloque, fuentes))
    finally:
        libro_cfg.close()

    rutas_fuente, faltantes = {}, []
    for _, fuentes in planes:
        for fuente in fuentes:
            ruta = resolver_fuente(fuente, indice, equivalencias)
            if ruta:
                rutas_fuente[fuente.archivo] = ruta
            elif fuente.archivo not in faltantes:
                faltantes.append(fuente.archivo)

    for nombre in faltantes:
        log.error('  ! no se encuentra la matriz «%s» en la unidad', nombre[:70])
    if faltantes:
        # Escribir un consolidado al que le faltan fuentes es peor que no
        # tocarlo: quedaría publicado incompleto y con apariencia de correcto.
        log.error('  NO se escribe %s: faltan %d fuente(s)', titulo, len(faltantes))
        return False

    # ¿Hace falta consolidar? No sirve comparar contra la fecha del consolidado:
    # la sincronización lo sobrescribe con el de Google en cada corrida, y esa
    # copia trae la fórmula muerta (llegó con `#VALUE!` y sin datos). Se compara
    # contra el estado que dejó la ÚLTIMA consolidación: si el destino ya no es
    # el que escribimos —porque Google lo pisó— hay que rehacerlo sí o sí.
    estado = leer_estado(definicion)
    destino_mtime = os.path.getmtime(ruta_destino)
    fuentes_mtime = max((os.path.getmtime(r) for r in rutas_fuente.values()), default=0)

    destino_pisado = estado.get('destino_mtime') != destino_mtime
    fuentes_nuevas = fuentes_mtime > estado.get('fuentes_mtime', 0)
    if not (destino_pisado or fuentes_nuevas or forzar):
        log.info('  sin cambios en las %d matrices: no se toca', len(rutas_fuente))
        return True
    if destino_pisado and estado:
        log.info('  el consolidado fue sobrescrito desde Google: se rehace')

    libro_salida = pagina_salida = None
    resumen = []
    filas_previas = 0
    if not prueba:
        libro_salida, pagina_salida = motor.abrir_destino(ruta_destino, definicion['hoja'])
        # Hasta dónde llegaba el bloque anterior. Si el consolidado encoge (una
        # matriz con menos filas), sin esto quedarían colgando las filas viejas
        # —que es justo lo que dejó la última consolidación hecha en Google.
        filas_previas = pagina_salida.max_row or 0

    lector = motor.LectorFuentes()
    bloques_escritos = []          # (celda, alto, ancho) para señalarlos en vivo
    fuentes_leidas = {}            # celda → [{archivo, hoja, rango, filas}] (caché)
    for bloque, fuentes in planes:
        matrices = []
        for fuente in fuentes:
            ruta = resolver_fuente(fuente, indice, equivalencias)
            if not ruta:
                continue
            matrices.append(lector.leer_rango(ruta, fuente.hoja, fuente.rango))
            fuentes_leidas.setdefault(bloque['destino'], []).append(
                {'archivo': ruta, 'hoja': fuente.hoja, 'rango': fuente.rango,
                 'filas': matrices[-1]})
        apilado = motor.apilar(matrices)
        resumen.append(f"  {bloque['nombre']}: {len(fuentes)} fuentes → "
                       f"{len(apilado)} filas × {len(apilado[0]) if apilado else 0} columnas "
                       f"en {bloque['destino']}")
        if not prueba:
            # Todos los bloques van sobre el MISMO libro: se guarda una sola vez.
            fila_inicial = coordinate_to_tuple(bloque['destino'])[0]
            motor.pegar(pagina_salida, bloque['destino'], apilado,
                        filas_a_limpiar=max(0, filas_previas - fila_inicial + 1))
            bloques_escritos.append((bloque['destino'], len(apilado),
                                     len(apilado[0]) if apilado else 0))

    lector.cerrar()
    for linea in resumen:
        log.info(linea)

    if prueba or libro_salida is None:
        return True

    carpeta_virtual, _, nombre = (BASE_VIRTUAL + '/' + definicion['archivo']).rpartition('/')

    # openpyxl guarda las fórmulas pero deja su resultado VACÍO (`<v></v>`), y así
    # los totales de cabecera aparecían en blanco. Se escribe a un temporal, se le
    # devuelven los resultados y se sube ya completo.
    # Nombre ÚNICO por corrida (11/09/2026): con un nombre fijo, la corrida de la
    # caja de arena (usuario sistemas) y la del cron (root) chocaban en /tmp, y
    # con fs.protected_regular root no puede sobrescribir un temporal ajeno.
    _fd, temporal = tempfile.mkstemp(prefix='consolidado-', suffix='.xlsx')
    os.close(_fd)
    libro_salida.save(temporal)
    libro_salida.close()
    try:
        ok_valores, puestos, motivo = completar(temporal)
        if ok_valores:
            log.info('  resultados de fórmulas rellenados: %d', puestos)
        else:
            log.warning('  no se pudieron rellenar los resultados (%s); se publica igual',
                        motivo)
        with open(temporal, 'rb') as fichero:
            memoria = io.BytesIO(fichero.read())
        memoria.seek(0)
        nucleo.subir(USUARIO, carpeta_virtual, nombre, memoria)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)
    guardar_estado(definicion, os.path.getmtime(ruta_destino), fuentes_mtime)
    log.info('  escrito y versionado: %s', nombre)
    # Caché por fuente: es lo que relee el camino rápido y lo que lee la API
    # en vivo. Se escribe antes de señalar, para que el editor lea lo nuevo.
    try:
        bloques_cache.guardar(ESTADO_DIR, definicion['archivo'], definicion['hoja'],
                              fuentes_leidas)
    except Exception as excepcion:
        log.warning('  caché de bloques: %s', excepcion)
    # Si alguien tiene el consolidado abierto, que le llegue ahora (en vivo).
    vivo.registrar_bloques(USUARIO, BASE_VIRTUAL + '/' + definicion['archivo'],
                           definicion['hoja'], bloques_escritos)
    return True


def main():
    forzar = '--forzar' in sys.argv
    prueba = '--prueba' in sys.argv
    # --solo <texto>: solo los consolidados cuyo nombre contenga ese texto
    # (para probar uno sin rehacer los cuatro).
    solo = sys.argv[sys.argv.index('--solo') + 1] if '--solo' in sys.argv else ''
    # --sandbox: la caja de arena de pruebas (copias en el Drive de Wilson),
    # misma lógica, otra carpeta. Nunca toca la unidad 12 (11/09/2026).
    if '--sandbox' in sys.argv:
        import sandbox
        sandbox.aplicar(globals())
        log.info('(caja de arena: %s)', BASE_VIRTUAL)
    log.info('=== Consolidados Planificación ASC ===')
    if prueba:
        log.info('(prueba: no se escribe nada)')
    indice = indice_de_archivos()
    equivalencias = mapa_ids_google()
    log.info('matrices localizadas en la unidad: %d (equivalencias por URL: %d)',
             len(indice), len(equivalencias))
    fallos = 0
    for definicion in CONSOLIDADOS:
        if solo and solo.lower() not in definicion['archivo'].lower():
            continue
        # En la caja de arena solo están los consolidados copiados: los demás se
        # saltan sin contarlos como fallo.
        if '--sandbox' in sys.argv and not os.path.isfile(
                os.path.join(BASE_FISICA, definicion['archivo'])):
            continue
        try:
            if not procesar(definicion, indice, equivalencias, forzar, prueba):
                fallos += 1
        except Exception as excepcion:          # una hoja rota no debe frenar la otra
            log.error('  ERROR en %s: %s', definicion['archivo'], excepcion)
            fallos += 1
    log.info('\nterminado con %d fallo(s)', fallos)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
