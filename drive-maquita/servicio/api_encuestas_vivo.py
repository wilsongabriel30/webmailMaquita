# -*- coding: utf-8 -*-
"""API de las respuestas en vivo en la hoja del formulario (21/09/2026).

Tres pasos, los que da el puente de la página del Drive en cada vuelta:

    GET  /api/almacen/encuestas/vivo/hojas?ruta=<libro>
         ¿hay respuestas pendientes para este libro? (barato, es el latido)

    POST /api/almacen/encuestas/vivo/filas
         {ruta, encuesta_id, encabezados: [...]}  → filas listas para escribir

    POST /api/almacen/encuestas/vivo/aplicado
         {ruta, encuesta_id, hasta, encabezados}  → ya está escrito en el editor

Se comprueba el acceso a la ruta en cada llamada (`ruta_fisica` falla cerrado).
El estado solo avanza en el tercer paso: si el editor no llega a escribir, la
respuesta sigue pendiente y la escribe el servidor cuando el libro se cierre.

Autoría: Equipo de Tecnología Maquita — 2026-09-21
"""
import logging

from flask import Blueprint, jsonify, request

import encuestas_vivo as vivo
from api_archivos import error, usuario_actual
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.encuestas.vivo.api')

bp_encuestas_vivo = Blueprint('encuestas_vivo', __name__)


def _ruta_pedida(origen):
    """Ruta del libro, ya comprobada contra los permisos de quien pregunta.

    Hace falta poder EDITAR el libro: con permiso de lectura el editor se abre
    en solo lectura, el complemento «escribe» en pantalla, se anotaba como
    escrito y nunca llegaba al archivo (28/09/2026, respuesta 258). Sin edición
    no hay nada que hacer aquí: la respuesta la escribe el servidor.
    """
    from api_archivos import _permiso_unidad
    usuario = usuario_actual()
    ruta = normalizar_ruta_virtual((origen.get('ruta') or '').strip())
    ruta_fisica(usuario, ruta)          # comprueba el acceso (falla cerrado)
    if not _permiso_unidad(usuario, ruta, escritura=True):
        raise RutaInvalida('Solo lectura: las respuestas las escribe el servidor', 403)
    return usuario, ruta


@bp_encuestas_vivo.route('/encuestas/vivo/hojas', methods=['GET'])
def hojas():
    try:
        usuario, ruta = _ruta_pedida(request.args)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    # Igual que en los vínculos: si este libro no tiene nada pendiente, se
    # recuerda y las preguntas siguientes se responden sin tocar la base.
    import vivo_sin_trabajo as sin_trabajo
    if sin_trabajo.esta_vacio(usuario, ruta):
        return jsonify({'success': True, 'hojas': []})
    hojas_pendientes = vivo.hojas_de(usuario, ruta)
    if not hojas_pendientes:
        sin_trabajo.recordar_vacio(usuario, ruta)
    return jsonify({'success': True, 'hojas': hojas_pendientes})


@bp_encuestas_vivo.route('/encuestas/vivo/filas', methods=['POST'])
def filas():
    cuerpo = request.get_json(silent=True) or {}
    try:
        usuario, ruta = _ruta_pedida(cuerpo)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    encabezados = cuerpo.get('encabezados')
    encuesta_id = (cuerpo.get('encuesta_id') or '').strip()
    if not encuesta_id or not isinstance(encabezados, list):
        return error('Faltan el formulario o los encabezados de la hoja', 400)
    datos = vivo.filas_para(usuario, ruta, encuesta_id,
                            [str(e or '') for e in encabezados])
    if datos is None:
        return error('Ese formulario no escribe en este libro', 404)
    return jsonify(dict({'success': True}, **datos))


@bp_encuestas_vivo.route('/encuestas/vivo/aplicado', methods=['POST'])
def aplicado():
    cuerpo = request.get_json(silent=True) or {}
    try:
        usuario, ruta = _ruta_pedida(cuerpo)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    encuesta_id = (cuerpo.get('encuesta_id') or '').strip()
    hasta = (cuerpo.get('hasta') or '').strip()
    encabezados = cuerpo.get('encabezados')
    if not encuesta_id or not hasta or not isinstance(encabezados, list):
        return error('Faltan datos para dar la escritura por buena', 400)
    try:
        hecho = vivo.confirmar(usuario, ruta, encuesta_id, hasta,
                               [str(e or '') for e in encabezados])
    except ValueError:
        return error('Marca de tiempo inválida', 400)
    if hecho:
        _guardar_ya(usuario, ruta)
    return jsonify({'success': bool(hecho)})


def _guardar_ya(usuario, ruta):
    """Pide al editor que guarde YA lo que acaba de escribir el complemento.

    Sin esto, la fila solo existe dentro de la sesión abierta hasta que todos
    cierran el libro: el archivo del disco no cambia y lo que depende de él
    —las copias «siempre al día», los vínculos— no se entera (28/09/2026). Con
    el guardado forzado, el callback deja el archivo en disco y refresca todo.
    Va en segundo plano y nunca falla hacia fuera.
    """
    import threading
    import time

    def trabajo():
        try:
            import guardado_forzado
            import nucleo_archivos as nucleo
            fisica = nucleo.ruta_fisica(int(usuario), ruta)
            for _ in range(3):              # el editor tarda un poco en registrar el cambio
                time.sleep(3)
                resultado = guardado_forzado.guardar_si_esta_abierto(
                    int(usuario), ruta, fisica, espera=20, forzar=True)
                if resultado != 'sin-cambios':
                    break
            log.info('vivo %s: guardado forzado tras escribir → %s', ruta, resultado)
        except Exception as excepcion:
            log.warning('vivo %s: no se pudo forzar el guardado (%s)', ruta, excepcion)
    threading.Thread(target=trabajo, name='vivo-guardar', daemon=True).start()
