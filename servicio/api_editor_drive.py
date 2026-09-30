# -*- coding: utf-8 -*-
"""
El editor (OnlyOffice) conectado con el Drive — lo que pide y nadie le daba
==========================================================================
El editor ofrece varias funciones que solo aparecen si la página que lo aloja
las atiende: «Guardar copia como…», «Imagen desde almacenamiento», «Crear
nuevo», plantillas, archivos recientes, cambiar el nombre desde la barra, etc.
Hasta el 23/09/2026 nadie las atendía y estaban apagadas o no hacían nada.

Este módulo pone las rutas del servidor. La parte del navegador está en
`estaticos/js/almacen/editor-drive.js` (se inyecta con `arreglos_editor`).

Rutas (montadas sobre bp_oo_drive, prefijo /api/almacen):
  POST /onlyoffice/guardar-como   {ruta, url, titulo, tipo}  → {ruta, nombre}
  POST /onlyoffice/imagen         {ruta, c}                  → datos firmados
                                                              para insertImage
  GET  /onlyoffice/recientes?ruta=  → archivos recientes del mismo tipo
  GET  /onlyoffice/plantillas?ruta= → plantillas del mismo tipo
Ruta web (sobre bp_onlyoffice_web):
  GET  /archivos-almacen/nuevo?carpeta=&tipo=xlsx[&desde=<plantilla>]
       crea el archivo en la carpeta y abre el editor.

Plantillas: cualquier archivo del tipo que esté en la carpeta «Plantillas» del
espacio personal o en la carpeta «Plantillas» de una unidad de la persona.

Autoría: Equipo de Tecnología Maquita — 2026-09-23
"""
import io
import logging
import os
import time
from urllib.parse import quote

import requests
from flask import jsonify, redirect, request

import nucleo_archivos as nucleo
import onlyoffice_urls as oo_urls
from almacen_bd import consultar
from api_archivos import _permiso_unidad, error, usuario_actual
from api_oo_drive import bp_oo_drive
from api_onlyoffice import (DIAS_TOKEN, EXTENSIONES_EDITABLES, TIPOS_DOCUMENTO,
                            bases_publicas_ds, bp_onlyoffice_web, firmar_jwt,
                            url_interna_ds)
from config_almacen import URL_PUBLICA
from registro import registrar_actividad
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.editor_drive')

DIR_VACIOS = '/home/sistemas/Maquita/modulos/nextcloud/recursos/plantillas'
NOMBRE_NUEVO = {'xlsx': 'Hoja de cálculo sin título', 'docx': 'Documento sin título',
                'pptx': 'Presentación sin título'}
EXT_IMAGEN = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg'}
CARPETA_PLANTILLAS = 'Plantillas'
TAMANO_MAXIMO = 200 * 1024 * 1024


def _ext(ruta):
    nombre = ruta.rsplit('/', 1)[-1]
    return nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''


def _existe(usuario, ruta):
    try:
        return os.path.exists(ruta_fisica(usuario, ruta))
    except RutaInvalida:
        return False


def nombre_libre(usuario, carpeta, nombre):
    """«X.xlsx», y si ya existe «X (1).xlsx», «X (2).xlsx»…"""
    base, punto, ext = nombre.rpartition('.')
    if not punto:
        base, ext = nombre, ''
    prefijo = '' if carpeta == '/' else carpeta
    candidato, n = nombre, 1
    while _existe(usuario, prefijo + '/' + candidato):
        candidato = '%s (%d)%s' % (base, n, ('.' + ext) if ext else '')
        n += 1
    return candidato


def _ruta(valor):
    return normalizar_ruta_virtual(valor or '')


def _url_editor(ruta):
    return '/archivos-almacen/editar?ruta=' + quote(ruta)


# ---------------------------------------------------------------------------
# «Guardar copia como…»: el editor convierte y nos da la URL del resultado
# ---------------------------------------------------------------------------
@bp_oo_drive.route('/onlyoffice/guardar-como', methods=['POST'])
def guardar_como():
    usuario = usuario_actual()
    datos = request.get_json(silent=True) or {}
    try:
        origen = _ruta(datos.get('ruta'))
    except RutaInvalida as exc:
        return error(str(exc), exc.codigo)
    carpeta = origen.rsplit('/', 1)[0] or '/'
    if not _permiso_unidad(usuario, carpeta, escritura=True):
        return error('No puedes guardar en esta carpeta', 403)

    # Solo se descarga del propio servidor de documentos (anti-SSRF), igual
    # que el guardado normal.
    url = oo_urls.a_url_interna(datos.get('url') or '', bases_publicas_ds(),
                                url_interna_ds())
    if not url:
        return error('La dirección del archivo no es del servidor de documentos', 400)
    tipo = (datos.get('tipo') or '').lower().strip('.')[:8]
    titulo = (datos.get('titulo') or '').strip() or origen.rsplit('/', 1)[-1]
    titulo = ''.join('-' if c in '\\/:*?"<>|' else c for c in titulo)[:150]
    if tipo and not titulo.lower().endswith('.' + tipo):
        titulo = titulo.rsplit('.', 1)[0] + '.' + tipo
    try:
        respuesta = requests.get(url, timeout=120, stream=True)
        respuesta.raise_for_status()
        contenido = respuesta.raw.read(TAMANO_MAXIMO + 1, decode_content=True)
    except Exception as exc:
        log.warning('guardar-como %s: %s', origen, exc)
        return error('No se pudo traer el archivo convertido', 502)
    if len(contenido) > TAMANO_MAXIMO:
        return error('El archivo es demasiado grande', 413)

    nombre = nombre_libre(usuario, carpeta, titulo)
    try:
        creado = nucleo.subir(usuario, carpeta, nombre, io.BytesIO(contenido))
    except Exception as exc:
        log.error('guardar-como %s: %s', origen, exc)
        return error('No se pudo guardar la copia', 500)
    ruta = creado.get('ruta') or (('' if carpeta == '/' else carpeta) + '/' + nombre)
    registrar_actividad(usuario, 'subio', ruta, 'copia de %s' % origen)
    return jsonify({'success': True, 'ruta': ruta, 'nombre': nombre,
                    'abrir': _url_editor(ruta) if _ext(ruta) in TIPOS_DOCUMENTO else ''})


# ---------------------------------------------------------------------------
# «Imagen desde almacenamiento»
# ---------------------------------------------------------------------------
@bp_oo_drive.route('/onlyoffice/imagen', methods=['POST'])
def imagen():
    usuario = usuario_actual()
    datos = request.get_json(silent=True) or {}
    try:
        ruta = _ruta(datos.get('ruta'))
    except RutaInvalida as exc:
        return error(str(exc), exc.codigo)
    ext = _ext(ruta)
    if ext not in EXT_IMAGEN:
        return error('Elige una imagen (png, jpg, gif, webp, svg…)', 400)
    if not _permiso_unidad(usuario, ruta, escritura=False) or not _existe(usuario, ruta):
        return error('No encontramos esa imagen', 404)
    exp = int(time.time()) + DIAS_TOKEN * 86400
    token = firmar_jwt({'u': usuario, 'r': ruta, 'uso': 'descarga', 'exp': exp})
    parametros = {
        'c': str(datos.get('c') or 'add')[:20],
        'images': [{'fileType': 'jpg' if ext == 'jpeg' else ext,
                    'url': f'{URL_PUBLICA}/api/almacen/onlyoffice/download?t={token}'}],
    }
    parametros['token'] = firmar_jwt(dict(parametros))
    return jsonify(parametros)


# ---------------------------------------------------------------------------
# Recientes y plantillas (menú Archivo del editor)
# ---------------------------------------------------------------------------
def _tipo_de(ruta):
    return TIPOS_DOCUMENTO.get(_ext(ruta))


@bp_oo_drive.route('/onlyoffice/recientes', methods=['GET'])
def recientes():
    usuario = usuario_actual()
    try:
        actual = _ruta(request.args.get('ruta'))
    except RutaInvalida as exc:
        return error(str(exc), exc.codigo)
    tipo = _tipo_de(actual)
    filas = consultar(
        "SELECT ruta, MAX(creado_en) AS f FROM actividad "
        "WHERE usuario_id = %s AND accion IN ('apertura','abrio','edito','subio') "
        "AND ruta <> %s AND creado_en > NOW() - INTERVAL '60 days' "
        "GROUP BY ruta ORDER BY f DESC LIMIT 60", (usuario, actual))
    lista = []
    for f in filas:
        ruta = f['ruta']
        if _tipo_de(ruta) != tipo or not _existe(usuario, ruta):
            continue
        lista.append({'title': ruta.rsplit('/', 1)[-1],
                      'folder': ruta.rsplit('/', 1)[0] or '/',
                      'modified': f['f'].strftime('%d/%m/%Y %H:%M'),
                      'url': _url_editor(ruta)})
        if len(lista) >= 12:
            break
    return jsonify({'success': True, 'recent': lista})


def _carpetas_de_plantillas(usuario):
    carpetas = ['/' + CARPETA_PLANTILLAS]
    try:
        for unidad in nucleo.listar_unidades(usuario):
            base = unidad.get('ruta') or ('/unidades/%s' % unidad.get('id'))
            carpetas.append(base.rstrip('/') + '/' + CARPETA_PLANTILLAS)
    except Exception as exc:
        log.debug('unidades para plantillas: %s', exc)
    return carpetas


@bp_oo_drive.route('/onlyoffice/plantillas', methods=['GET'])
def plantillas():
    usuario = usuario_actual()
    try:
        actual = _ruta(request.args.get('ruta'))
    except RutaInvalida as exc:
        return error(str(exc), exc.codigo)
    tipo = _tipo_de(actual)
    ext_nueva = {'cell': 'xlsx', 'word': 'docx', 'slide': 'pptx'}.get(tipo, _ext(actual))
    carpeta_actual = actual.rsplit('/', 1)[0] or '/'
    lista = []
    for carpeta in _carpetas_de_plantillas(usuario):
        if not _existe(usuario, carpeta) or not _permiso_unidad(usuario, carpeta):
            continue
        try:
            fis = ruta_fisica(usuario, carpeta)
            for nombre in sorted(os.listdir(fis)):
                ruta = carpeta + '/' + nombre
                # Solo las que se pueden editar (xlsx, ods…): una .xltx o una
                # .whiteboard abriría en solo lectura o en otro programa.
                if (_tipo_de(ruta) != tipo or _ext(ruta) not in EXTENSIONES_EDITABLES
                        or not os.path.isfile(os.path.join(fis, nombre))):
                    continue
                lista.append({
                    'title': nombre.rsplit('.', 1)[0],
                    'url': '/archivos-almacen/nuevo?carpeta=%s&tipo=%s&desde=%s'
                           % (quote(carpeta_actual), ext_nueva, quote(ruta)),
                })
        except OSError:
            continue
    return jsonify({'success': True, 'templates': lista[:40],
                    'crear': '/archivos-almacen/nuevo?carpeta=%s&tipo=%s'
                             % (quote(carpeta_actual), ext_nueva)})


# ---------------------------------------------------------------------------
# «Crear nuevo» (en blanco o desde una plantilla) → abre el editor
# ---------------------------------------------------------------------------
@bp_onlyoffice_web.route('/archivos-almacen/nuevo')
def nuevo():
    usuario = usuario_actual()
    try:
        carpeta = _ruta(request.args.get('carpeta') or '/')
    except RutaInvalida:
        carpeta = '/'
    ext = (request.args.get('tipo') or 'xlsx').lower()
    if ext not in NOMBRE_NUEVO:
        ext = 'xlsx'
    if not _permiso_unidad(usuario, carpeta, escritura=True):
        carpeta = '/'          # sin permiso aquí: a Mi unidad, que siempre es suya
    desde = request.args.get('desde')
    contenido, nombre = None, NOMBRE_NUEVO[ext] + '.' + ext
    if desde:
        try:
            plantilla = _ruta(desde)
            # La copia conserva el formato de la plantilla (una .ods sigue .ods).
            if (_permiso_unidad(usuario, plantilla)
                    and _tipo_de(plantilla) == _tipo_de('x.' + ext)
                    and _ext(plantilla) in EXTENSIONES_EDITABLES
                    and '/' + CARPETA_PLANTILLAS + '/' in plantilla):
                with open(ruta_fisica(usuario, plantilla), 'rb') as f:
                    contenido = f.read()
                nombre = plantilla.rsplit('/', 1)[-1]
        except (RutaInvalida, OSError) as exc:
            log.warning('plantilla %s: %s', desde, exc)
    if contenido is None:
        with open(os.path.join(DIR_VACIOS, 'vacio.' + ext), 'rb') as f:
            contenido = f.read()
    nombre = nombre_libre(usuario, carpeta, nombre)
    creado = nucleo.subir(usuario, carpeta, nombre, io.BytesIO(contenido))
    ruta = creado.get('ruta') or (('' if carpeta == '/' else carpeta) + '/' + nombre)
    registrar_actividad(usuario, 'subio', ruta, 'nuevo desde el editor')
    return redirect(_url_editor(ruta), 302)
