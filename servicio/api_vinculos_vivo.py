# -*- coding: utf-8 -*-
"""Respuestas «en vivo» en un libro ABIERTO en el editor (11/09/2026).

El servidor no puede meter datos en una sesión abierta de OnlyOffice (el
siguiente guardado del editor pisa lo que se escriba en disco). Quien sí puede
es un complemento que corre DENTRO del editor. Este módulo es lo que ese
complemento —a través de la página del Drive, que tiene la sesión— pregunta:

    GET /api/almacen/vinculos/vivo?ruta=<libro>&desde=<marca>

Devuelve los vínculos cuyo destino es ese libro y, para los que cambiaron
después de `desde`, la tabla completa del origen (cabeceras y filas) lista
para escribirla en su hoja. Con `desde` vacío devuelve todo (al abrir el libro
se rellena entero: así también se corrige lo que hubiera quedado atrasado).

Es de solo lectura y barato: una consulta a la base cada pocos segundos por
libro abierto, y solo se lee un archivo de origen cuando de verdad cambió.
"""
import datetime
import logging

from flask import Blueprint, jsonify, request

import almacen_bd as bd
from api_archivos import error, usuario_actual
from archivos_internos import en_carpeta_interna
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.vinculos.vivo')

bp_vinculos_vivo = Blueprint('vinculos_vivo', __name__)


def _celda_json(valor):
    """Fecha → texto que el editor entiende como fecha (formato local)."""
    if isinstance(valor, datetime.datetime):
        return valor.strftime('%d/%m/%Y %H:%M:%S')
    if isinstance(valor, datetime.date):
        return valor.strftime('%d/%m/%Y')
    if valor is None:
        return ''
    return valor


def _recortar(matriz):
    """Quita filas y columnas vacías del final: la tabla, no el rango entero."""
    filas = [list(f) for f in matriz]
    while filas and all(c in (None, '') for c in filas[-1]):
        filas.pop()
    ancho = 0
    for f in filas:
        for j in range(len(f) - 1, -1, -1):
            if f[j] not in (None, ''):
                ancho = max(ancho, j + 1)
                break
    return [[_celda_json(c) for c in f[:ancho]] for f in filas]


def _bloque_de_cache(ruta, celda):
    from consolidados import bloques_cache, rutas_estado
    return bloques_cache.bloque_apilado(rutas_estado.estado_dir_de(ruta), ruta, celda)


def _cache_mas_nueva(usuario, ruta):
    """¿La caché de bloques es más reciente que el archivo del consolidado?"""
    try:
        import os
        from consolidados import bloques_cache, rutas_estado
        return (bloques_cache.mtime(rutas_estado.estado_dir_de(ruta), ruta)
                > os.path.getmtime(ruta_fisica(usuario, ruta)))
    except Exception:
        return False


@bp_vinculos_vivo.route('/vinculos/vivo', methods=['GET'])
def vivo():
    usuario = usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
        ruta_fisica(usuario, ruta)          # comprueba el acceso (falla cerrado)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    desde = (request.args.get('desde') or '').strip()

    filas = bd.consultar(
        'SELECT id, origen_usuario, origen_ruta, origen_hoja, origen_rango, '
        '       destino_hoja, destino_celda, destino_hoja_previa, actualizado_en '
        '  FROM vinculos_datos WHERE activo AND destino_ruta = %s '
        '   AND (destino_usuario = %s OR destino_ruta LIKE %s) ORDER BY id',
        (ruta, int(usuario), '/unidades/%'))

    from api_vinculos import _leer_rango
    salida, ahora = [], None
    for v in filas:
        marca = v['actualizado_en'].isoformat() if v['actualizado_en'] else ''
        ahora = max(ahora or '', marca)
        item = {'id': v['id'], 'hoja': v['destino_hoja'],
                'celda': v['destino_celda'], 'actualizado_en': marca,
                # Renombre pendiente (el título cambió con el libro abierto):
                # el complemento renombra la pestaña en vivo y avisa (`aplicado`).
                'hoja_previa': v.get('destino_hoja_previa') or '',
                # Solo las hojas de respuestas de formularios llevan formato
                # propio (cabecera en negrita, fecha). Un vínculo entre libros
                # o un consolidado respeta el formato que ya tenga la hoja.
                'formulario': en_carpeta_interna(v['origen_ruta'])}
        autovinculo = v['origen_ruta'] == ruta
        if autovinculo:
            # Consolidado ASC: el bloque sale de la caché por fuente (la
            # escribe la consolidación y el camino rápido). Al abrir solo se
            # rellena si la caché es más nueva que el archivo del disco.
            if (marca > desde) if desde else _cache_mas_nueva(usuario, ruta):
                try:
                    bloque = _bloque_de_cache(ruta, v['destino_celda'])
                    if bloque is None:
                        bloque = _leer_rango(v['origen_usuario'], v['origen_ruta'],
                                             v['origen_hoja'], v['origen_rango'])
                    item['filas'] = _recortar(bloque)
                except Exception as excepcion:
                    log.warning('vivo %s: no se pudo leer el bloque (%s)', v['id'], excepcion)
        elif (marca > desde) if desde else True:
            try:
                item['filas'] = _recortar(_leer_rango(
                    v['origen_usuario'], v['origen_ruta'],
                    v['origen_hoja'], v['origen_rango']))
            except Exception as excepcion:
                log.warning('vivo %s: no se pudo leer el origen (%s)', v['id'], excepcion)
        salida.append(item)
    return jsonify({'success': True, 'vinculos': salida, 'ahora': ahora or desde})


@bp_vinculos_vivo.route('/vinculos/vivo/aplicado', methods=['POST'])
def aplicado():
    """El complemento ya renombró la pestaña en el editor: se limpia la
    anotación para que el servidor no lo repita al cerrar el libro."""
    usuario = usuario_actual()
    try:
        vinculo_id = int(request.args.get('id', ''))
    except ValueError:
        return error('Vínculo inválido', 400)
    bd.ejecutar(
        'UPDATE vinculos_datos SET destino_hoja_previa = NULL '
        ' WHERE id = %s AND (destino_usuario = %s OR destino_ruta LIKE %s)',
        (vinculo_id, int(usuario), '/unidades/%'))
    return jsonify({'success': True})
