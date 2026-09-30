# -*- coding: utf-8 -*-
"""
Rutas de «Publicar en la web» (Drive Maquita). La lógica está en publicar_web.py.

  GET  /api/almacen/publicar-web?ruta=A.xlsx   → hojas y publicaciones de ese archivo
  POST /api/almacen/publicar-web               {ruta, hoja?} → publica (o devuelve la que hay)
  POST /api/almacen/publicar-web/quitar        {id}          → deja de publicar
  GET  /w/<token>[?h=N][&formato=csv]          página pública (sin sesión)

Quién puede publicar: lo mismo que para sacar un enlace público. En el espacio
personal, su dueño; en una unidad compartida, solo quien la administra
(`manager`), igual que en api_compartir: lo que sale de una unidad lo decide
quien la administra.

Autoría: Equipo de Tecnología Maquita — 2026-09-23
"""
import logging
import os
from urllib.parse import quote

from flask import Response, jsonify, request

import almacen_bd as bd
import publicar_web as pw
from api_archivos import _efectivo, _permiso_unidad, bp_archivos, error, usuario_actual
from api_onlyoffice import bp_onlyoffice_web
from config_almacen import URL_LINKS
from registro import registrar_actividad
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.api.publicar_web')

EXTENSIONES = ('.xlsx', '.xlsm')


def _url(token):
    return '%s/w/%s' % (URL_LINKS, token)


def _puede_publicar(usuario, ruta):
    """(sí/no, motivo)."""
    if ruta.startswith('/unidades/'):
        try:
            unidad_id = int(ruta.split('/')[2])
        except (IndexError, ValueError):
            return False, 'Ruta de unidad no válida'
        from roles_unidad import rol_en_unidad
        if rol_en_unidad(usuario, unidad_id) != 'manager':
            return False, ('Solo el administrador de la unidad compartida puede publicar '
                           'su documentación en la web.')
        return True, ''
    dueno, _ = _efectivo(usuario, ruta)
    if int(dueno) != int(usuario):
        return False, 'Solo quien es dueño del archivo puede publicarlo en la web.'
    return True, ''


def _pedida(valor):
    ruta = normalizar_ruta_virtual(valor or '')
    if not ruta.lower().endswith(EXTENSIONES):
        raise RutaInvalida('Solo se pueden publicar hojas de cálculo (.xlsx)')
    return ruta


def _ficha(p):
    return {'id': p['id'], 'hoja': p['hoja'], 'url': _url(p['token']),
            'vistas': p['vistas'], 'creado_en': p['creado_en'].isoformat()}


@bp_archivos.route('/publicar-web', methods=['GET'])
def publicaciones():
    usuario = usuario_actual()
    try:
        ruta = _pedida(request.args.get('ruta'))
    except RutaInvalida as exc:
        return error(str(exc), exc.codigo)
    if not _permiso_unidad(usuario, ruta):
        return error('No tienes acceso a este archivo', 403)
    dueno, ruta_ef = _efectivo(usuario, ruta)
    try:
        libro = pw._leer(ruta_fisica(dueno, ruta_ef))
        hojas = [ws.title for ws in pw.hojas_visibles(libro)]
        libro.close()
    except Exception as exc:
        log.warning('hojas de %s: %s', ruta, exc)
        return error('No se pudo leer el libro', 500)
    puede, motivo = _puede_publicar(usuario, ruta)
    return jsonify({'success': True, 'hojas': hojas, 'puede': puede, 'motivo': motivo,
                    'publicaciones': [_ficha(p) for p in pw.de_ruta(dueno, ruta_ef)]})


@bp_archivos.route('/publicar-web', methods=['POST'])
def publicar():
    usuario = usuario_actual()
    datos = request.get_json(silent=True) or {}
    try:
        ruta = _pedida(datos.get('ruta'))
    except RutaInvalida as exc:
        return error(str(exc), exc.codigo)
    puede, motivo = _puede_publicar(usuario, ruta)
    if not puede:
        return error(motivo, 403)
    dueno, ruta_ef = _efectivo(usuario, ruta)
    if not os.path.isfile(ruta_fisica(dueno, ruta_ef)):
        return error('El archivo no existe', 404)
    hoja = (datos.get('hoja') or '').strip() or None
    p = pw.publicar(dueno, ruta_ef, hoja, usuario)
    registrar_actividad(usuario, 'publico_web', ruta, hoja or 'todas las hojas')
    return jsonify({'success': True, 'publicacion': _ficha(p)})


@bp_archivos.route('/publicar-web/quitar', methods=['POST'])
def quitar():
    usuario = usuario_actual()
    pid = (request.get_json(silent=True) or {}).get('id')
    filas = bd.consultar('SELECT * FROM publicaciones_web WHERE id = %s AND activo',
                         (int(pid or 0),))
    if not filas:
        return error('Esa publicación ya no existe', 404)
    p = filas[0]
    puede, motivo = _puede_publicar(usuario, p['ruta']) if p['ruta'].startswith('/unidades/') \
        else (int(p['usuario_id']) == int(usuario), 'Solo quien lo publicó puede retirarlo.')
    if not puede:
        return error(motivo, 403)
    pw.despublicar(p['id'])
    registrar_actividad(usuario, 'despublico_web', p['ruta'], p['hoja'] or '')
    return jsonify({'success': True})


@bp_onlyoffice_web.route('/w/<token>')
def pagina_publica(token):
    """La hoja publicada. Sin sesión: su seguridad es el token."""
    no_hay = Response('<!DOCTYPE html><meta charset="utf-8"><title>No disponible</title>'
                      '<p style="font:16px Arial;padding:24px">Esta hoja ya no está publicada '
                      'o el enlace no es correcto.</p>', status=404, mimetype='text/html')
    p = pw.por_token(token)
    if not p:
        return no_hay
    try:
        fisica = ruta_fisica(p['usuario_id'], p['ruta'])
        if not os.path.isfile(fisica):
            return no_hay
        formato = 'csv' if request.args.get('formato') == 'csv' else 'html'
        datos = pw.render(fisica, p['ruta'].rsplit('/', 1)[-1], p['hoja'],
                          request.args.get('h', 0), formato)
    except LookupError:
        return no_hay
    except Exception as exc:
        log.error('publicación %s (%s): %s', p['id'], p['ruta'], exc)
        return Response('No se pudo mostrar la hoja en este momento.', status=500)
    if formato == 'csv':
        nombre = p['ruta'].rsplit('/', 1)[-1].rsplit('.', 1)[0] + '.csv'
        respuesta = Response(datos, mimetype='text/csv; charset=utf-8')
        respuesta.headers['Content-Disposition'] = "attachment; filename*=UTF-8''" + quote(nombre)
    else:
        pw.contar_vista(p['id'])
        respuesta = Response(datos, mimetype='text/html; charset=utf-8')
    # Siempre al día, pero sin rehacerla en cada visita seguida.
    respuesta.headers['Cache-Control'] = 'public, max-age=60'
    respuesta.headers['X-Robots-Tag'] = 'noindex'
    return respuesta
