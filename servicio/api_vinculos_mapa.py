# -*- coding: utf-8 -*-
"""
Vínculos de datos — de un vistazo, en las dos direcciones (Drive Maquita)
=========================================================================
`/vinculos/listar` dice de qué archivos BEBE este. Faltaba lo contrario: QUIÉN
BEBE DE ÉL. Desde la hoja de respuestas de un formulario es lo que uno quiere
saber —qué archivos se alimentan de ella y cuándo se refrescaron por última
vez—, y hasta ahora no se veía por ningún lado (22/09/2026).

Ruta (montada sobre bp_vinculos, mismo prefijo /api/almacen):
  GET /vinculos/mapa?ruta=A.xlsx
      → {entrantes: [...], salientes: [...]}
        entrantes: lo que este archivo TRAE de otros (se puede quitar aquí).
        salientes: los archivos que se alimentan de este. Si el destino es de
                   otra persona, se ve pero no se toca: su vínculo es suyo.

Autoría: Equipo de Tecnología Maquita — 2026-09-22
"""
import logging

from flask import jsonify, request

import almacen_bd as bd
import api_vinculos as _v
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual

log = logging.getLogger('almacen.api.vinculos.mapa')


def _ficha(fila, propio):
    """Una línea de la lista, con lo justo para entenderla sin abrir nada."""
    return {
        'id': fila['id'],
        'origen_ruta': fila['origen_ruta'],
        'origen_nombre': fila['origen_ruta'].rsplit('/', 1)[-1],
        'origen_hoja': fila['origen_hoja'],
        'origen_rango': fila['origen_rango'],
        'destino_ruta': fila['destino_ruta'],
        'destino_nombre': fila['destino_ruta'].rsplit('/', 1)[-1],
        'destino_hoja': fila['destino_hoja'],
        'destino_celda': fila['destino_celda'],
        'actualizado_en': fila['actualizado_en'].isoformat() if fila['actualizado_en'] else '',
        'mio': bool(propio),
    }


@_v.bp_vinculos.route('/vinculos/mapa', methods=['GET'])
def mapa():
    """GET /vinculos/mapa?ruta= — las conexiones de este archivo, en ambos sentidos."""
    usuario = _v.usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
    except RutaInvalida as excepcion:
        return _v.error(str(excepcion), excepcion.codigo)

    entrantes = bd.consultar(
        'SELECT id, origen_ruta, origen_hoja, origen_rango, destino_ruta, '
        '       destino_hoja, destino_celda, actualizado_en '
        '  FROM vinculos_datos WHERE activo AND destino_usuario = %s '
        '   AND destino_ruta = %s AND origen_ruta <> destino_ruta ORDER BY id',
        (usuario, ruta))
    # Salientes: los de cualquiera, porque una hoja de respuestas de una unidad
    # puede alimentar el libro de otra persona; se marca cuáles son míos.
    salientes = bd.consultar(
        'SELECT id, origen_ruta, origen_hoja, origen_rango, destino_ruta, '
        '       destino_hoja, destino_celda, actualizado_en, destino_usuario '
        '  FROM vinculos_datos WHERE activo AND origen_ruta = %s '
        '   AND origen_ruta <> destino_ruta ORDER BY id', (ruta,))
    import espejos_hoja
    esp_entrantes, esp_salientes = espejos_hoja.mapa(usuario, ruta)
    try:                             # libros que reciben respuestas de un formulario
        import api_formulario_destinos
        esp_entrantes = esp_entrantes + api_formulario_destinos.mapa(usuario, ruta)
    except Exception as excepcion:
        log.warning('mapa %s: destinos de formulario (%s)', ruta, excepcion)
    return jsonify({
        'success': True,
        'entrantes': [_ficha(f, True) for f in entrantes] + esp_entrantes,
        'salientes': [_ficha(f, f['destino_usuario'] == usuario) for f in salientes]
                     + esp_salientes,
    })


@_v.bp_vinculos.route('/espejos/eliminar', methods=['POST'])
def eliminar_espejo():
    """POST /espejos/eliminar {id} — la copia deja de actualizarse (se queda)."""
    import espejos_hoja
    from api_archivos import _permiso_unidad
    usuario = _v.usuario_actual()
    espejo = espejos_hoja.obtener((request.get_json(silent=True) or {}).get('id') or 0)
    if not espejo:
        return _v.error('Esa conexión ya no existe', 404)
    ruta = espejo['destino_ruta']
    propio = espejo['destino_usuario'] == usuario
    if not propio and not (ruta.startswith('/unidades/') and _permiso_unidad(
            usuario, ruta.rsplit('/', 1)[0] or '/', escritura=True)):
        return _v.error('Solo quien puede editar la copia puede quitar la conexión', 403)
    espejos_hoja.desactivar(espejo['id'])
    return jsonify({'success': True})
