# -*- coding: utf-8 -*-
"""
Sacar una hoja de un libro a su propio archivo, desde el Drive (Drive Maquita).

Por qué existe: «Mover o copiar» del editor se lleva la pestaña CON sus
fórmulas. Si esa hoja se alimentaba de otra del mismo libro, en el archivo
nuevo la hoja de origen no existe y todo queda en `#¿NOMBRE?` (las diez
pestañas de provincia de «prueba IFO», 22/09/2026). Desde aquí la hoja sale ya
congelada: con su formato, su tabla y su imagen, pero con valores en vez de
fórmulas.

Rutas (montadas sobre bp_archivos, mismo prefijo /api/almacen):
  GET  /archivos/hojas?ruta=A.xlsx          → {hojas: [...], dependencias: {hoja: [...]}}
  POST /archivos/extraer-hoja               → {ruta, hoja, nombre?, contenido?, modo?}
       crea «<nombre>.xlsx» en la misma carpeta (sin pisar otro) y devuelve su ruta.
       contenido: «valores» (por defecto) | «propias» (conserva las fórmulas de
       la propia hoja; las que tomaban datos de otra quedan con su valor) |
       «formulas» (todas, con sus hojas de origen ocultas).
       modo: espejo | bloque | congelada.

Permisos: los mismos que el resto del explorador (`_permiso_unidad` para leer
el libro y para escribir en la carpeta destino).

Autoría: Equipo de Tecnología Maquita — 2026-09-22
"""
import io
import logging
import os
import re

from flask import jsonify, request

import api_archivos as _api
import hoja_a_archivo as extractor
import nucleo_archivos as nucleo
from registro import registrar_actividad
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.api.hoja')

EXTENSIONES = ('.xlsx', '.xlsm')


def _libro_pedido(origen, escritura=False):
    """(usuario, ruta, bytes) del libro, comprobando el acceso."""
    usuario = _api.usuario_actual()
    ruta = normalizar_ruta_virtual((origen.get('ruta') or '').strip())
    if not ruta.lower().endswith(EXTENSIONES):
        raise RutaInvalida('Eso no es una hoja de cálculo')
    if not _api._permiso_unidad(usuario, ruta, escritura=escritura):
        raise RutaInvalida('No tienes permiso sobre ese archivo', 403)
    fisica = ruta_fisica(usuario, ruta)
    if not os.path.isfile(fisica):
        raise RutaInvalida('Ese archivo ya no existe', 404)
    return usuario, ruta, open(fisica, 'rb').read()


@_api.bp_archivos.route('/archivos/hojas', methods=['GET'])
def hojas_del_libro():
    """GET /archivos/hojas?ruta= — las pestañas del libro, para poder elegir."""
    try:
        _usuario, ruta, contenido = _libro_pedido(request.args)
    except RutaInvalida as excepcion:
        return jsonify({'success': False, 'error': str(excepcion)}), excepcion.codigo
    try:
        hojas = extractor.hojas_de(contenido)
    except Exception as excepcion:
        log.warning('hojas de %s: %s', ruta, excepcion)
        return jsonify({'success': False, 'error': 'No se pudo leer el libro'}), 500
    # De qué hojas depende cada una: el diálogo lo muestra al elegir «con
    # fórmulas». Si no se puede calcular, el diálogo funciona igual sin ello.
    try:
        import hoja_dependencias
        dependencias = hoja_dependencias.todas(contenido)
        formulas = hoja_dependencias.contar_formulas(contenido)
    except Exception as excepcion:
        log.warning('dependencias de %s: %s', ruta, excepcion)
        dependencias, formulas = {}, {}
    # ¿Puede crear el archivo nuevo junto al libro? Un lector de la carpeta no:
    # el diálogo le propone guardarlo en su Mi unidad (28/09/2026).
    carpeta = ruta.rsplit('/', 1)[0] or '/'
    return jsonify({'success': True, 'hojas': hojas, 'dependencias': dependencias,
                    'formulas': formulas, 'origen': _origen(ruta),
                    'puede_escribir': bool(_api._permiso_unidad(_usuario, carpeta + '/x',
                                                                escritura=True))})


def _origen(ruta):
    """Qué es este libro, para avisar si «Siempre al día» no va a recibir nada:
    un adjunto guardado del correo no cambia nunca (28/09/2026: se extrajo de
    «Archivos del correo/…/prueba IFO (respuestas) (1).xlsx» y las copias
    «siempre al día» no se movían). Si es la hoja de un formulario, se dice."""
    if ruta.startswith('/Archivos del correo/'):
        return {'tipo': 'adjunto'}
    try:
        import almacen_bd as bd
        filas = bd.consultar('SELECT titulo FROM encuestas WHERE hoja_ruta = %s LIMIT 1', (ruta,))
        if filas:
            return {'tipo': 'formulario', 'formulario': filas[0]['titulo'] or ''}
    except Exception as excepcion:
        log.info('origen de %s: %s', ruta, excepcion)
    return {'tipo': 'libro'}


@_api.bp_archivos.route('/archivos/extraer-hoja', methods=['POST'])
def extraer_hoja():
    """POST /archivos/extraer-hoja — {ruta, hoja, nombre?} → archivo nuevo."""
    cuerpo = request.get_json(silent=True) or {}
    try:
        usuario, ruta, contenido = _libro_pedido(cuerpo)
    except RutaInvalida as excepcion:
        return jsonify({'success': False, 'error': str(excepcion)}), excepcion.codigo
    hoja = (cuerpo.get('hoja') or '').strip()
    if not hoja:
        return jsonify({'success': False, 'error': 'Falta la hoja'}), 400

    # Dónde se guarda: junto al libro («aqui») o en Mi unidad («mi_unidad»),
    # para quien solo puede leer la carpeta del libro (28/09/2026).
    carpeta = ruta.rsplit('/', 1)[0] or '/'
    if cuerpo.get('donde') == 'mi_unidad':
        carpeta = '/'
    elif not _api._permiso_unidad(usuario, carpeta + '/x', escritura=True):
        return jsonify({'success': False, 'sin_permiso': True,
                        'error': 'Solo puedes leer la carpeta de este libro: no puedes crear '
                                 'archivos ahí. Guárdalo en tu Mi unidad.'}), 403
    pedido = (cuerpo.get('nombre') or hoja).strip()
    nombre = re.sub(r'[\\/:*?"<>|]', '-', pedido)[:80].strip() or hoja
    if not nombre.lower().endswith('.xlsx'):
        nombre += '.xlsx'
    # Nunca se pisa un archivo que ya esté en la carpeta: «X (1).xlsx».
    try:
        from api_editor_drive import nombre_libre
        nombre = nombre_libre(usuario, carpeta, nombre)
    except Exception as excepcion:
        log.warning('nombre libre para %s: %s', nombre, excepcion)

    que = cuerpo.get('contenido') or 'valores'
    if que not in extractor.QUE:
        return jsonify({'success': False, 'error': 'Contenido desconocido'}), 400
    modo = cuerpo.get('modo') or ('bloque' if cuerpo.get('vincular') else 'congelada')
    if modo not in ('espejo', 'bloque', 'congelada'):
        return jsonify({'success': False, 'error': 'Modo desconocido'}), 400
    if que != 'valores' and modo == 'bloque':
        # «Solo la tabla» copia valores dentro de un rango: con fórmulas no aplica.
        modo = 'espejo'
    ocultas = []
    try:
        salida = extractor.extraer(contenido, hoja, que=que)
        if que == 'formulas':
            import hoja_dependencias
            ocultas = hoja_dependencias.dependencias(
                hoja_dependencias.leer_libro(contenido), hoja)
    except extractor.SinLaHoja:
        return jsonify({'success': False, 'error': 'Ese libro no tiene la hoja «%s»' % hoja}), 404
    except Exception as excepcion:
        log.warning('extraer %s de %s: %s', hoja, ruta, excepcion)
        return jsonify({'success': False, 'error': 'No se pudo preparar la hoja'}), 500

    try:
        creado = nucleo.subir(usuario, carpeta, nombre, io.BytesIO(salida))
    except Exception as excepcion:
        log.error('extraer %s de %s: no se pudo guardar (%s)', hoja, ruta, excepcion)
        return jsonify({'success': False, 'error': 'No se pudo guardar el archivo'}), 500
    registrar_actividad(usuario, 'creo', creado['ruta'], 'hoja «%s» de %s%s' % (
        hoja, ruta, {'propias': ' (con sus fórmulas)',
                     'formulas': ' (con fórmulas y hojas de origen)'}.get(que, '')))

    # «Mantener actualizado»: se deja un vínculo de datos del rango de esa hoja
    # al archivo nuevo. A partir de ahí, cada respuesta que llegue al libro de
    # origen lo refresca solo (`api_vinculos.refrescar_por_origen`).
    #
    # Modos (23/09/2026): «espejo» = copia fiel de la HOJA COMPLETA (título,
    # formato, filas y columnas nuevas); «bloque» = solo el rango de la tabla,
    # como antes; «congelada» = sin conexión. Sin `modo`, se respeta el
    # `vincular` de los clientes que aún tengan el diálogo anterior en caché.
    # Con fórmulas (28/09/2026) el espejo rehace la copia del mismo modo.
    aviso = ''
    if modo == 'espejo':
        import espejos_hoja
        try:
            bien, motivo = espejos_hoja.crear(usuario, ruta, hoja, creado['ruta'],
                                              que=que)
            if not bien:
                aviso = 'Se creó la conexión, pero no se pudo actualizar ahora: %s' % motivo
        except Exception as excepcion:
            log.warning('espejo %s de %s: %s', creado['ruta'], ruta, excepcion)
            aviso = 'El archivo se creó, pero no se pudo dejar conectado.'
    elif modo == 'bloque':
        aviso = _vincular(usuario, ruta, hoja, contenido, creado['ruta'])
    try:                                   # lo que de verdad lleva el archivo nuevo
        import hoja_dependencias
        formulas_copia = hoja_dependencias.contar_formulas(salida).get(hoja, 0)
    except Exception:
        formulas_copia = None
    return jsonify({'success': True, 'ruta': creado['ruta'], 'nombre': nombre,
                    'carpeta': 'mi_unidad' if cuerpo.get('donde') == 'mi_unidad' else 'aqui',
                    'formulas': formulas_copia, 'origen_nombre': ruta.rsplit('/', 1)[-1],
                    'vinculado': modo != 'congelada' and not aviso,
                    'modo': modo, 'contenido': que,
                    'ocultas': ocultas, 'aviso': aviso})


def _vincular(usuario, origen, hoja, contenido, destino):
    """Conecta la copia con la hoja de la que salió. Devuelve '' si todo fue
    bien, o el motivo por el que no se pudo (el archivo ya está creado: que no
    se pueda vincular no debe deshacerlo)."""
    try:
        rango = extractor.rango_de(contenido, hoja)
        if not rango:
            return 'La hoja está vacía: no se creó la conexión.'
        import almacen_bd as bd
        import api_vinculos as vinculos
        fila = bd.ejecutar(
            """INSERT INTO vinculos_datos
               (origen_usuario, origen_ruta, origen_hoja, origen_rango,
                destino_usuario, destino_ruta, destino_hoja, destino_celda, creado_por)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (usuario, origen, hoja, rango[0], usuario, destino, hoja, rango[1], usuario))
        bien, motivo = vinculos._refrescar(dict(fila))
        return '' if bien else 'Se creó la conexión, pero no se pudo traer los datos ahora: %s' % motivo
    except Exception as excepcion:
        log.warning('vincular %s con %s: %s', destino, origen, excepcion)
        return 'El archivo se creó, pero no se pudo dejar conectado.'
