"""API del control de macros — Almacén Maquita.

Expone dos cosas:

  GET /macros/estado?ruta=...      ¿este archivo tiene macros?
  GET /macros/copia-limpia?ruta=…  descarga la copia SIN macros

La copia limpia conserva el MISMO formato, con datos, fórmulas, formato,
hojas y gráficos intactos. Solo se le quita la macro. Se descartó entregar un
PDF —que fue la primera idea— porque perdía las fórmulas sin necesidad: las
macros de OnlyOffice son JavaScript y el Excel de quien recibe el archivo no
las ejecutaría de todos modos.

Ver la política completa en
`00-CLAUDE-CONTEXTO/EDICION-REFERENCIAS-Y-MACROS-ONLYOFFICE.md`.
"""

import logging
import os
import tempfile

from flask import Blueprint, jsonify, request, send_file

import macros
from api_archivos import error, usuario_actual
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.macros')

bp_macros = Blueprint('almacen_macros', __name__)


def _archivo_pedido():
    """Resuelve y valida la ruta pedida. Devuelve (usuario, ruta, física)."""
    usuario = usuario_actual()
    ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
    if ruta == '/':
        raise RutaInvalida('Ruta no válida')
    fisica = ruta_fisica(usuario, ruta)
    if not os.path.isfile(fisica):
        raise RutaInvalida('El archivo no existe')
    return usuario, ruta, fisica


@bp_macros.route('/macros/estado', methods=['GET'])
def estado():
    """¿El archivo tiene macros? Lo usa el explorador para avisar antes de
    que la persona intente compartir y se lleve un rechazo sin contexto."""
    try:
        _usuario, ruta, fisica = _archivo_pedido()
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)

    nombre = ruta.rsplit('/', 1)[-1]
    con_macros = macros.tiene_macros(fisica, nombre)
    return jsonify({
        'success': True,
        'tiene_macros': con_macros,
        'compartible': not con_macros,
        'nombre_copia_limpia': (macros.nombre_copia_limpia(nombre)
                                if con_macros else None),
        'motivo': ('Las macros son de uso interno de Maquita: este archivo no '
                   'se comparte fuera. Se puede compartir la copia sin macros, '
                   'que conserva datos, fórmulas y formato.')
        if con_macros else None,
    })


@bp_macros.route('/macros/copia-limpia', methods=['GET'])
def copia_limpia():
    """Descarga una copia del archivo SIN macros, en su mismo formato."""
    try:
        usuario, ruta, fisica = _archivo_pedido()
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)

    nombre = ruta.rsplit('/', 1)[-1]

    if macros.necesita_conversion(nombre):
        # .doc/.xls/.ppt (contenedor OLE) y .xlsb no son ZIP: no se les puede
        # quitar la macro reescribiendo el envase, hay que convertirlos al
        # formato moderno. Antes había que hacerlo a mano desde el editor; hoy
        # lo hace el Document Server, que al no soportar VBA devuelve el
        # archivo ya sin macro (conversion_ds lo verifica antes de entregarlo).
        import conversion_ds
        convertido, nombre_limpio = conversion_ds.copia_sin_macros(
            usuario, ruta, nombre)
        if not convertido:
            return error(
                'Este archivo está en un formato antiguo (%s) y no se pudo '
                'convertir automáticamente. Abrilo en el editor y usá '
                '«Archivo → Descargar como» para guardarlo en %s.'
                % (macros.extension_de(nombre).upper(),
                   macros.extension_de(macros.nombre_copia_limpia(nombre)).upper()),
                415)

        log.info('Copia sin macros (convertida) de %s entregada a usuario %s',
                 ruta, usuario)
        respuesta = send_file(convertido, as_attachment=True,
                              download_name=nombre_limpio)
        respuesta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'

        @respuesta.call_on_close
        def _borrar_convertido():
            try:
                os.unlink(convertido)
            except OSError:
                pass
        return respuesta

    temporal = None
    try:
        descriptor, temporal = tempfile.mkstemp(prefix='sin-macros-')
        os.close(descriptor)
        nombre_limpio = macros.limpiar(fisica, nombre, temporal)
        if not nombre_limpio:
            return error('No se pudo generar la copia sin macros', 500)

        log.info('Copia sin macros de %s entregada a usuario %s',
                 ruta, usuario)

        respuesta = send_file(temporal, as_attachment=True,
                              download_name=nombre_limpio)
        # El archivo original puede cambiar; esta copia se genera al vuelo y
        # no debe quedarse guardada en ningún sitio.
        respuesta.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'

        @respuesta.call_on_close
        def _borrar():
            try:
                os.unlink(temporal)
            except OSError:
                pass

        return respuesta

    except Exception as excepcion:
        if temporal and os.path.exists(temporal):
            try:
                os.unlink(temporal)
            except OSError:
                pass
        log.exception('Fallo generando la copia sin macros de %s', ruta)
        return error('No se pudo generar la copia sin macros: %s' % excepcion,
                     500)
