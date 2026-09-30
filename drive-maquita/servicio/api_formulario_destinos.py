# -*- coding: utf-8 -*-
"""
Recibir respuestas de un formulario en un Excel propio — rutas (28/09/2026)
==========================================================================
Montadas sobre bp_vinculos (prefijo /api/almacen), como «Ver conexiones»:

  GET  /formularios-destino/formularios?ruta=<xlsx>
       → {hojas: [...], formularios: [{encuesta_id, titulo, ubicacion}]}
         (los formularios cuyas respuestas puede ver quien pregunta)
  POST /formularios-destino/vista   {ruta, hoja, encuesta_id, filtro_pregunta?, filtro_valor?}
       → cómo encajan las columnas, preguntas para filtrar y cuántas entrarían
  POST /formularios-destino/crear   {ruta, hoja, encuesta_id, filtro_pregunta?,
                                     filtro_valor?, solo_nuevas?}
  POST /formularios-destino/eliminar {id}

Permisos: escribir en el libro de destino y poder ver las respuestas del
formulario (lectura en su carpeta, igual que «Ver respuestas»).

Autoría: Equipo de Tecnología Maquita — 2026-09-28
"""
import logging
import os

from flask import jsonify, request

import api_vinculos as _v
import formulario_destinos as destinos
import formulario_destinos_xml as lugar_mod
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.api.formulario_destinos')

EXTENSIONES = ('.xlsx', '.xlsm')


def _permiso(usuario, ruta, escritura):
    from api_archivos import _permiso_unidad
    return _permiso_unidad(usuario, ruta.rsplit('/', 1)[0] or '/', escritura=escritura)


def _libro(origen, escritura=True):
    """(usuario, ruta, bytes) del Excel de destino, comprobando el acceso."""
    usuario = _v.usuario_actual()
    ruta = normalizar_ruta_virtual((origen.get('ruta') or '').strip())
    if not ruta.lower().endswith(EXTENSIONES):
        raise RutaInvalida('Eso no es una hoja de cálculo')
    if not _permiso(usuario, ruta, escritura):
        raise RutaInvalida('No puedes editar este archivo', 403)
    fisica = ruta_fisica(usuario, ruta)
    if not os.path.isfile(fisica):
        raise RutaInvalida('Ese archivo ya no existe', 404)
    return usuario, ruta, open(fisica, 'rb').read()


def _puede_ver(usuario, fila):
    """¿Puede esta persona ver las respuestas de este formulario?"""
    if fila['ruta'].startswith('/unidades/'):
        return _permiso(usuario, fila['ruta'], False)
    return int(fila['propietario']) == int(usuario)


def _formulario_permitido(usuario, encuesta_id):
    fila, definicion = destinos.formulario(encuesta_id)
    if definicion is None or not _puede_ver(usuario, fila):
        raise RutaInvalida('No puedes ver las respuestas de ese formulario', 403)
    return fila, definicion


def _ubicacion(ruta, nombres_unidad):
    """«Unidad Planificación ASC · IBI 2026», «Mi unidad · Encuestas»…"""
    carpeta = ruta.rsplit('/', 1)[0] or '/'
    if carpeta.startswith('/unidades/'):
        partes = carpeta.split('/', 3)
        nombre = nombres_unidad.get(partes[2], 'compartida')
        return 'Unidad %s' % nombre + (' · ' + partes[3] if len(partes) > 3 and partes[3] else '')
    return 'Mi unidad' + ('' if carpeta == '/' else ' · ' + carpeta.lstrip('/'))


@_v.bp_vinculos.route('/formularios-destino/formularios', methods=['GET'])
def destino_formularios():
    try:
        usuario, _ruta, contenido = _libro(request.args)
    except RutaInvalida as excepcion:
        return _v.error(str(excepcion), excepcion.codigo)
    import hoja_a_archivo
    from api_encuestas import leer_definicion
    nombres_unidad = {str(u['id']): u['nombre'] for u in destinos.bd.consultar(
        'SELECT id, nombre FROM unidades_compartidas')}
    salida, vistos = [], set()
    for fila in destinos.bd.consultar(
            "SELECT id, titulo, ruta, propietario FROM encuestas "
            "WHERE propietario = %s OR ruta LIKE '/unidades/%%' ORDER BY titulo", (usuario,)):
        # Un mismo `.forma` puede tener varias filas antiguas en el registro: el
        # formulario es el archivo, y su id de verdad es el que lleva dentro.
        clave = fila['ruta'] if fila['ruta'].startswith('/unidades/') \
            else (fila['propietario'], fila['ruta'])
        if clave in vistos or not _puede_ver(usuario, fila):
            continue
        vistos.add(clave)
        try:
            definicion = leer_definicion(int(fila['propietario']), fila['ruta'])
        except Exception:
            definicion = None
        if not definicion:                       # ya no está en el Drive
            continue
        salida.append({'encuesta_id': definicion['id'],
                       'titulo': fila['titulo'] or '(sin título)',
                       'ubicacion': _ubicacion(fila['ruta'], nombres_unidad)})
    return jsonify({'success': True, 'hojas': hoja_a_archivo.hojas_de(contenido),
                    'formularios': salida})


def _preguntas_para_filtrar(listado):
    import encuestas_modelo as modelo
    salida = []
    for p in listado:
        if p['tipo'] in ('archivo',) or p['tipo'] in modelo.TIPOS_CUADRICULA:
            continue
        opciones = [modelo.plano(o.get('texto') if isinstance(o, dict) else o)
                    for o in (p.get('opciones') or [])] if p['tipo'] in modelo.TIPOS_CON_OPCIONES else []
        salida.append({'id': p['id'], 'titulo': modelo.plano(p['titulo']),
                       'opciones': [o for o in opciones if o]})
    return salida


@_v.bp_vinculos.route('/formularios-destino/vista', methods=['POST'])
def destino_vista():
    cuerpo = request.get_json(silent=True) or {}
    try:
        usuario, _ruta, contenido = _libro(cuerpo)
        fila, definicion = _formulario_permitido(usuario, (cuerpo.get('encuesta_id') or '').strip())
    except RutaInvalida as excepcion:
        return _v.error(str(excepcion), excepcion.codigo)
    d = {'filtro_pregunta': cuerpo.get('filtro_pregunta') or None,
         'filtro_valor': cuerpo.get('filtro_valor') or '', 'escritas': [], 'desde': None}
    datos = destinos.respuestas(fila, definicion, d)
    base = {'success': True, 'preguntas': _preguntas_para_filtrar(datos['listado']),
            'total': len(datos['lista'])}
    try:
        lugar = lugar_mod.localizar(contenido, (cuerpo.get('hoja') or '').strip(),
                                    datos['cabeceras'])
    except lugar_mod.SinDondeEscribir as excepcion:
        return jsonify(dict(base, encaja=False, motivo=str(excepcion)))
    n_fijas = len(datos['cabeceras']) - len(datos['listado'])
    mapa = destinos.mapa_columnas(lugar['encabezados'], datos['cabeceras'], n_fijas)
    fechas = lugar_mod.fechas_presentes(lugar)
    faltan = destinos.pendientes(d, datos, fechas)
    usadas = set(mapa.values())
    import openpyxl.utils as utiles
    return jsonify(dict(
        base, encaja=True,
        fila_encabezados=lugar['f1'],
        rango='%s%d:%s' % (utiles.get_column_letter(lugar['c1']), lugar['f1'],
                           utiles.get_column_letter(lugar['c2'])),
        coinciden=[lugar['encabezados'][i] for i in sorted(mapa)],
        propias=[e for i, e in enumerate(lugar['encabezados']) if i not in mapa and e],
        sin_columna=[c for j, c in enumerate(datos['cabeceras']) if j not in usadas],
        con_fecha=fechas is not None,
        ya_estan=len(datos['lista']) - len(faltan),
        faltan=len(faltan)))


@_v.bp_vinculos.route('/formularios-destino/crear', methods=['POST'])
def destino_crear():
    cuerpo = request.get_json(silent=True) or {}
    try:
        usuario, ruta, contenido = _libro(cuerpo)
        encuesta_id = (cuerpo.get('encuesta_id') or '').strip()
        fila, definicion = _formulario_permitido(usuario, encuesta_id)
    except RutaInvalida as excepcion:
        return _v.error(str(excepcion), excepcion.codigo)
    hoja = (cuerpo.get('hoja') or '').strip()
    import hoja_a_archivo
    if hoja not in hoja_a_archivo.hojas_de(contenido):
        return _v.error('Elige una hoja de este archivo', 400)
    import encuestas_hoja as hoja_mod
    try:
        lugar_mod.localizar(contenido, hoja, hoja_mod.cabeceras(fila, definicion))
    except lugar_mod.SinDondeEscribir as excepcion:
        return _v.error(str(excepcion), 400)
    filtro_pregunta = (cuerpo.get('filtro_pregunta') or '').strip() or None
    filtro_valor = (cuerpo.get('filtro_valor') or '').strip()
    if filtro_pregunta and not filtro_valor:
        return _v.error('Escribe o elige el valor del filtro', 400)
    for d in destinos.de_la_ruta(usuario, ruta):
        if d['encuesta_id'] == encuesta_id and d['destino_hoja'] == hoja \
                and (d['filtro_pregunta'] or None) == filtro_pregunta \
                and (d['filtro_valor'] or '') == (filtro_valor if filtro_pregunta else ''):
            return _v.error('Esta hoja ya recibe esas respuestas', 409)
    d = destinos.crear(usuario, encuesta_id, ruta, hoja, filtro_pregunta, filtro_valor,
                       bool(cuerpo.get('solo_nuevas')))
    abierto = bool(hoja_mod._sala_ocupada(usuario, ruta))
    if not abierto:
        destinos.escribir_en_segundo_plano(d)
    from registro import registrar_actividad
    registrar_actividad(usuario, 'conecto', ruta, 'recibe respuestas de «%s» en la hoja «%s»'
                        % (fila.get('titulo') or '', hoja))
    return jsonify({'success': True, 'id': d['id'], 'abierto': abierto})


@_v.bp_vinculos.route('/formularios-destino/eliminar', methods=['POST'])
def destino_eliminar():
    usuario = _v.usuario_actual()
    d = destinos.obtener((request.get_json(silent=True) or {}).get('id') or 0)
    if not d:
        return _v.error('Esa conexión ya no existe', 404)
    if int(d['destino_usuario']) != int(usuario) and not (
            d['destino_ruta'].startswith('/unidades/') and _permiso(usuario, d['destino_ruta'], True)):
        return _v.error('Solo quien puede editar el archivo puede quitar la conexión', 403)
    destinos.desactivar(d['id'])
    return jsonify({'success': True})


def mapa(usuario, ruta):
    """Fichas para «Ver conexiones» (entrantes de este libro)."""
    salida = []
    for d in destinos.de_la_ruta(usuario, ruta):
        fila, definicion = destinos.formulario(d['encuesta_id'])
        filtro = 'todas las respuestas'
        if d.get('filtro_pregunta') and definicion:
            import encuestas_modelo as modelo
            pregunta = next((p for p in modelo.preguntas(definicion)
                             if p['id'] == d['filtro_pregunta']), None)
            filtro = 'solo %s = %s' % (modelo.plano(pregunta['titulo']) if pregunta else '?',
                                       d.get('filtro_valor') or '')
        salida.append({
            'id': d['id'], 'tipo': 'formulario',
            'origen_ruta': (fila or {}).get('ruta', ''),
            'origen_nombre': 'Formulario «%s»' % ((fila or {}).get('titulo') or '?'),
            'origen_hoja': 'respuestas', 'origen_rango': filtro,
            'destino_ruta': d['destino_ruta'],
            'destino_nombre': d['destino_ruta'].rsplit('/', 1)[-1],
            'destino_hoja': d['destino_hoja'], 'destino_celda': 'filas nuevas',
            'actualizado_en': d['actualizado_en'].isoformat() if d.get('actualizado_en') else '',
            'error': d.get('ultimo_error') or '', 'mio': True,
        })
    return salida
