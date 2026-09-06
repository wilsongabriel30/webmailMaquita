# -*- coding: utf-8 -*-
"""
API de extras del Almacén Maquita.
==================================
Favoritos, papelera (listar/restaurar/vaciar) y enlaces públicos servidos
sin login (/archivos/s/<token>). Completan el uso diario estilo Drive.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import logging
import os

from flask import Blueprint, jsonify, request, send_file, abort

import nucleo_archivos as nucleo
from almacen_bd import consultar, ejecutar
from api_archivos import error, usuario_actual
from seguridad_rutas import RutaInvalida, ruta_fisica

log = logging.getLogger('almacen.extras')

bp_extras = Blueprint('almacen_extras', __name__)


# ── favoritos ────────────────────────────────────────────────────────────
@bp_extras.route('/archivos/favorito', methods=['POST'])
def toggle_favorito():
    """POST /archivos/favorito — {ruta}. Marca/desmarca; devuelve el nuevo estado."""
    usuario = usuario_actual()
    datos = request.get_json() or {}
    if not datos.get('ruta'):
        return error('Ruta requerida', 400)
    try:
        es_favorito = nucleo.toggle_favorito(usuario, datos['ruta'])
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    return jsonify({'success': True, 'es_favorito': es_favorito})


@bp_extras.route('/favoritos', methods=['GET'])
def listar_favoritos():
    """GET /favoritos — items marcados como favoritos."""
    usuario = usuario_actual()
    carpetas, archivos = nucleo.listar_favoritos(usuario)
    return jsonify({'success': True, 'carpetas': carpetas, 'archivos': archivos,
                    'total': len(carpetas) + len(archivos)})


# ── papelera ─────────────────────────────────────────────────────────────
@bp_extras.route('/papelera', methods=['GET'])
def listar_papelera():
    """GET /papelera — contenido de la papelera del usuario."""
    usuario = usuario_actual()
    carpetas, archivos = nucleo.listar_papelera(usuario)
    return jsonify({'success': True, 'carpetas': carpetas, 'archivos': archivos,
                    'total': len(carpetas) + len(archivos)})


@bp_extras.route('/papelera/restaurar', methods=['POST'])
def restaurar_de_papelera():
    """POST /papelera/restaurar — {ruta}. 'ruta' es el identificador en la papelera."""
    usuario = usuario_actual()
    datos = request.get_json() or {}
    if not datos.get('ruta'):
        return error('Ruta requerida', 400)
    try:
        restaurada = nucleo.restaurar_de_papelera(usuario, datos['ruta'])
    except FileNotFoundError:
        return error('No está en la papelera', 404)
    # T-18: si vuelve un archivo del chat, el chat lo muestra de nuevo
    try:
        from hook_chat import avisar_chat
        avisar_chat(usuario, restaurada, 'restaurado')
    except Exception:
        pass
    return jsonify({'success': True, 'ruta_restaurada': restaurada})


@bp_extras.route('/papelera/vaciar', methods=['POST'])
def vaciar_papelera():
    """POST /papelera/vaciar — el usuario vacía su papelera.
    NO se destruye: pasa a la retención de 90 días (recuperable solo por master)."""
    usuario = usuario_actual()
    movidos = nucleo.vaciar_papelera(usuario)
    return jsonify({'success': True, 'message': 'Papelera vaciada',
                    'retenidos': movidos})


# ── enlaces públicos (sin login) ────────────────────────────────────────
@bp_extras.route('/publico-info/<token>', methods=['GET', 'POST'])
def info_publico(token):
    """GET/POST /publico-info/<token> — datos del enlace para la página pública (sin sesión).
    [F-08] La clave va en la cabecera X-Clave-Enlace o en el cuerpo JSON, nunca en la URL."""
    from clave_enlace import CABECERAS_PUBLICAS, comprobar_clave
    from almacen_bd import conexion, ejecutar
    filas = consultar("""
        SELECT token, propietario_id, ruta, expira_en, clave_hash, permite_descarga, puede_editar
        FROM compartidos WHERE token = %s
    """, (token,))
    if not filas:
        return error('Enlace no encontrado', 404)
    comp = filas[0]
    if comp['expira_en'] is not None:
        from datetime import datetime, timezone
        if comp['expira_en'] < datetime.now(timezone.utc):
            return error('El enlace expiró', 410)
    requiere_clave = bool(comp['clave_hash'])
    if requiere_clave:
        ok, codigo = comprobar_clave(conexion, comp, ejecutar)
        if codigo == 429:
            return error('Demasiados intentos; espera unos minutos', 429)
        if not ok:
            return jsonify({'success': True, 'requiere_clave': True,
                            'clave_valida': False}), 200, CABECERAS_PUBLICAS
    nombre = comp['ruta'].rsplit('/', 1)[-1]
    extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''
    from api_onlyoffice import EXTENSIONES_EDITABLES, TIPOS_DOCUMENTO
    abre_en_linea = extension in TIPOS_DOCUMENTO
    tamano = None
    try:
        fisica = ruta_fisica(comp['propietario_id'], comp['ruta'])
        if os.path.isfile(fisica):
            tamano = os.path.getsize(fisica)
    except RutaInvalida:
        pass
    return jsonify({
        'success': True, 'requiere_clave': requiere_clave, 'clave_valida': True,
        'nombre': nombre, 'extension': extension,
        'tamano_bytes': tamano,
        'permite_descarga': bool(comp['permite_descarga']),
        'puede_editar': bool(comp['puede_editar']) and extension in EXTENSIONES_EDITABLES,
        'abre_en_linea': abre_en_linea,
    }), 200, CABECERAS_PUBLICAS


@bp_extras.route('/publico/<token>', methods=['GET', 'POST'])
def descargar_publico(token):
    """
    GET/POST /api/nextcloud/publico/<token> — descarga por enlace público, SIN login.
    Valida token, expiración y (si tiene) clave; [F-08] la clave va en cabecera o cuerpo.
    """
    from clave_enlace import CABECERAS_PUBLICAS, comprobar_clave
    from almacen_bd import conexion, ejecutar
    filas = consultar("""
        SELECT token, propietario_id, ruta, expira_en, clave_hash, permite_descarga
        FROM compartidos WHERE token = %s AND tipo = 3
    """, (token,))
    if not filas:
        abort(404)
    comp = filas[0]
    if not comp.get('permite_descarga', True):
        return error('Este enlace es de solo lectura (descarga no permitida)', 403)
    if comp['expira_en'] is not None:
        from datetime import datetime, timezone
        if comp['expira_en'] < datetime.now(timezone.utc):
            return error('El enlace expiró', 410)
    if comp['clave_hash']:
        ok, codigo = comprobar_clave(conexion, comp, ejecutar)
        if codigo == 429:
            return error('Demasiados intentos; espera unos minutos', 429)
        if not ok:
            return error('Clave incorrecta', 401)
    try:
        fisica = ruta_fisica(comp['propietario_id'], comp['ruta'])
    except RutaInvalida:
        abort(404)
    if not os.path.isfile(fisica):
        abort(404)
    respuesta = send_file(fisica, as_attachment=True, download_name=os.path.basename(fisica))
    for k, v in CABECERAS_PUBLICAS.items():
        respuesta.headers[k] = v
    return respuesta


