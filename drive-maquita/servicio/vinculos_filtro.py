# -*- coding: utf-8 -*-
"""Vínculos de datos con FILTRO y APILADOS: lo que faltaba para que la gente
rehaga por sí sola lo que en Google hacía QUERY(IMPORTRANGE(...)).

Responsabilidad ÚNICA: dado un vínculo, armar la matriz que hay que escribir
en su destino. Antes era «el rango del origen tal cual»; ahora puede ser:

  · con filtro: solo las filas cuya columna X tiene uno de los valores dados
    (`filtro_columna`, `filtro_valores`), como `SELECT * WHERE O = 'ASC - …'`;
  · apilado: varios vínculos sobre el MISMO destino (`apilar_id` apunta al
    primero, la «cabeza») se escriben uno debajo de otro, como
    `QUERY({IMPORTRANGE(a); IMPORTRANGE(b)})`.

La columna del filtro se escribe como en Google: la letra de la columna en la
hoja de origen («O»), o «Col8» contando desde la primera columna del rango.
Los valores van separados por «|». La comparación no distingue mayúsculas,
tildes ni espacios sobrantes: «asc - comunicacion» encuentra «ASC - Comunicación».

Creado 30/09/2026. Lo usan api_vinculos (refresco y creación) y
api_vinculos_vivo (el libro abierto en el editor).
"""
import logging
import re
import unicodedata

from openpyxl.utils import column_index_from_string, range_boundaries

import almacen_bd as bd

log = logging.getLogger('almacen.vinculos.filtro')

_asegurado = False


def asegurar_columnas():
    """Las tres columnas nuevas de `vinculos_datos` (idempotente)."""
    global _asegurado
    if _asegurado:
        return
    with bd.conexion() as con:
        with con.cursor() as cur:
            cur.execute("""
                ALTER TABLE vinculos_datos ADD COLUMN IF NOT EXISTS filtro_columna TEXT;
                ALTER TABLE vinculos_datos ADD COLUMN IF NOT EXISTS filtro_valores TEXT;
                ALTER TABLE vinculos_datos ADD COLUMN IF NOT EXISTS apilar_id INTEGER;
                ALTER TABLE vinculos_datos ADD COLUMN IF NOT EXISTS ultimo_alto INTEGER;
            """)
    _asegurado = True


def _plano(texto):
    """Sin tildes, sin mayúsculas, sin espacios repetidos: para comparar."""
    t = unicodedata.normalize('NFD', str(texto if texto is not None else ''))
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', t).strip().lower()


def indice_columna(columna, rango):
    """Posición (0-based, dentro del rango) de la columna del filtro."""
    columna = (columna or '').strip()
    min_c = range_boundaries(rango)[0]
    m = re.match(r'^col\s*(\d+)$', columna, re.I)
    if m:
        return int(m.group(1)) - 1
    if re.match(r'^\d+$', columna):
        return int(columna) - 1
    if re.match(r'^[A-Za-z]{1,3}$', columna):
        return column_index_from_string(columna.upper()) - min_c
    raise ValueError('Columna de filtro no válida: %r' % columna)


def valores_lista(texto):
    return [v.strip() for v in str(texto or '').split('|') if v.strip()]


def filtrar(matriz, rango, columna, valores):
    """Las filas de `matriz` (leída de `rango`) cuya columna tiene uno de `valores`."""
    idx = indice_columna(columna, rango)
    buscados = {_plano(v) for v in valores}
    return [f for f in matriz if idx < len(f) and _plano(f[idx]) in buscados]


def _sin_cola(matriz):
    filas = [list(f) for f in matriz]
    while filas and all(c in (None, '') for c in filas[-1]):
        filas.pop()
    return filas


def cabeza(v):
    """El vínculo que manda sobre el destino: él mismo, o al que se apila."""
    if not v.get('apilar_id'):
        return dict(v)
    filas = bd.consultar('SELECT * FROM vinculos_datos WHERE id = %s', (int(v['apilar_id']),))
    return dict(filas[0]) if filas else dict(v)


def miembros(cabeza_id):
    """Los vínculos apilados debajo de la cabeza, en orden."""
    return [dict(f) for f in bd.consultar(
        'SELECT * FROM vinculos_datos WHERE activo AND apilar_id = %s ORDER BY id',
        (int(cabeza_id),))]


def matriz_de(v, leer_rango, puede_leer=None):
    """(matriz, cabeza): lo que hay que escribir en el destino de la cabeza.

    `leer_rango(usuario, ruta, hoja, rango)` es el lector de api_vinculos;
    `puede_leer(usuario_destino, usuario_origen, ruta_origen)` revalida el
    permiso de cada origen apilado (si se da). Un origen que falle se anota y
    se salta: el resto de la pila sigue entrando.
    """
    asegurar_columnas()
    cab = cabeza(v)
    partes = [cab] + miembros(cab['id'])
    salida = []
    for parte in partes:
        try:
            if puede_leer and not puede_leer(cab['destino_usuario'], parte['origen_usuario'],
                                             parte['origen_ruta']):
                log.warning('vínculo %s: sin permiso vigente sobre el origen', parte['id'])
                continue
            filas = _sin_cola(leer_rango(parte['origen_usuario'], parte['origen_ruta'],
                                         parte['origen_hoja'], parte['origen_rango']))
            if parte.get('filtro_columna') and parte.get('filtro_valores'):
                filas = filtrar(filas, parte['origen_rango'], parte['filtro_columna'],
                                valores_lista(parte['filtro_valores']))
            salida.extend(filas)
        except Exception as excepcion:
            if parte is cab:
                raise
            log.warning('vínculo apilado %s: %s', parte.get('id'), excepcion)
    ancho = max((len(f) for f in salida), default=0)
    return [list(f) + [None] * (ancho - len(f)) for f in salida], cab
