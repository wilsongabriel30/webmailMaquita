"""
Formularios del Almacén — publicar como encuesta de campo (10/11/2026)
=====================================================================
    GET  /api/almacen/encuestas/campo?ruta=…              → estado (versiones, caducidad, cambios sin publicar)
    POST /api/almacen/encuestas/campo/publicar?ruta=…     {caduca: 'AAAA-MM-DDTHH:MM'} → publica la versión
    POST /api/almacen/encuestas/campo/quitar?ruta=…       → deja de ser encuesta de campo

La lógica vive en `encuestas_versiones.py`. Lo importa `api_encuestas_publico`
al final, como los demás complementos de los formularios.

Autoría: Equipo de Tecnología Maquita — 2026-11-10
"""
import logging

from flask import jsonify, request

import encuestas_bd as ebd
import encuestas_campo_permiso as permiso_campo
import encuestas_versiones as versiones
from api_encuestas import (_abrir, _limpiar_definicion, _resumen, _sincronizar_bd, bp_encuestas,
                           error, usuario_actual)

log = logging.getLogger('almacen.api.encuestas.versiones')


def _ruta():
    """Ruta del formulario pedido, para el permiso por territorio; None si no se puede leer."""
    try:
        from api_encuestas import _ruta_pedida
        return _ruta_pedida()
    except Exception:
        return None


def _estado(fila, definicion, puede=None):
    """Estado de campo más lo que el editor necesita: el id y si esta persona puede publicar."""
    campo = versiones.estado(fila, definicion)
    campo['id'] = definicion.get('id')
    campo['puede_publicar'] = permiso_campo.puede_publicar(usuario_actual(), _ruta()) if puede is None else puede
    return campo


def _sin_permiso():
    if permiso_campo.puede_publicar(usuario_actual(), _ruta()):
        return None
    return error(permiso_campo.MENSAJE, 403)


def _preparar(escritura):
    datos, fallo = _abrir(escritura=escritura)
    if fallo:
        return None, fallo
    usuario, ruta, definicion = datos
    definicion = _limpiar_definicion(definicion)
    fila = _sincronizar_bd(usuario, ruta, definicion)
    return (usuario, ruta, definicion, fila), None


@bp_encuestas.route('/encuestas/campo', methods=['GET'])
def estado_campo():
    datos, fallo = _preparar(False)
    if fallo:
        return fallo
    _usuario, _ruta, definicion, fila = datos
    return jsonify({'success': True, 'campo': _estado(fila, definicion)})


@bp_encuestas.route('/encuestas/campo/publicar', methods=['POST'])
def publicar_campo():
    negado = _sin_permiso()
    if negado:
        return negado
    datos, fallo = _preparar(True)
    if fallo:
        return fallo
    _usuario, _ruta, definicion, fila = datos
    cuerpo = request.get_json(silent=True) or {}
    quien = usuario_actual()
    try:
        numero, nueva = versiones.publicar(fila, definicion, quien, cuerpo.get('caduca'))
    except versiones.PublicacionInvalida as e:
        return error(str(e), 400)
    fila = ebd.obtener(definicion['id'])
    log.info('encuesta de campo %s: versión %s (%s) por %s', definicion['id'], numero,
             'nueva' if nueva else 'misma', quien)
    return jsonify({'success': True, 'version': numero, 'nueva': nueva,
                    'campo': _estado(fila, definicion, True), 'estado': _resumen(fila, definicion)})


@bp_encuestas.route('/encuestas/campo/quitar', methods=['POST'])
def quitar_campo():
    negado = _sin_permiso()
    if negado:
        return negado
    datos, fallo = _preparar(True)
    if fallo:
        return fallo
    _usuario, _ruta, definicion, fila = datos
    versiones.quitar(fila)
    fila = ebd.obtener(definicion['id'])
    return jsonify({'success': True, 'campo': _estado(fila, definicion, True),
                    'estado': _resumen(fila, definicion)})
