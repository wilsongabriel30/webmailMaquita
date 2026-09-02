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
        return error(str(excepcion), 400)
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
    # Restaurar deja contenido en una carpeta: hace falta poder escribir ahi.
    # Importa cuando a alguien le cambian el rol despues de haber borrado algo.
    from permisos_accion import puede_escribir, carpeta_de, MOTIVO_LECTOR
    origen = nucleo.ruta_original_en_papelera(usuario, datos['ruta'])
    if origen and not puede_escribir(usuario, carpeta_de(origen)):
        return error(MOTIVO_LECTOR, 403)
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
    from almacen_bd import consultar
    antes = consultar('SELECT COUNT(*) AS n FROM papelera WHERE usuario_id = %s AND unidad_id IS NULL',
                      (usuario,))[0]['n']
    movidos = nucleo.vaciar_papelera(usuario)
    # Solo la papelera personal: los elementos de unidades compartidas se vacían aparte
    quedan = consultar('SELECT COUNT(*) AS n FROM papelera WHERE usuario_id = %s AND unidad_id IS NULL',
                       (usuario,))[0]['n']
    # Antes esto devolvia 'exito' pasara lo que pasara. Si la carpeta de
    # retencion no se podia escribir, movidos era 0, la papelera seguia llena
    # y el usuario veia «Papelera vaciada» sin que se vaciara nada: el error mas
    # confuso posible, el que dice que todo fue bien. Ahora se dice la verdad.
    if quedan:
        return jsonify({
            'success': False,
            'message': ('No se pudo vaciar la papelera: %d de %d elementos no se '
                        'pudieron mover a la retención. Tus archivos siguen a '
                        'salvo en la papelera. Avisá a Tecnología.'
                        % (quedan, antes)),
            'retenidos': movidos, 'pendientes': quedan}), 500
    return jsonify({'success': True,
                    'message': 'Papelera vaciada (%d elemento%s a retención)'
                               % (movidos, '' if movidos == 1 else 's'),
                    'retenidos': movidos})


@bp_extras.route('/papelera/eliminar', methods=['POST'])
def eliminar_item_papelera():
    """POST /papelera/eliminar — {ruta}. Elimina UN item de la papelera.
    'ruta' es el identificador en la papelera (nombre_fisico). NO se destruye:
    pasa a la retención de 90 días (recuperable solo por master)."""
    usuario = usuario_actual()
    datos = request.get_json() or {}
    if not datos.get('ruta'):
        return error('Ruta requerida', 400)
    try:
        nucleo.eliminar_de_papelera(usuario, datos['ruta'])
    except FileNotFoundError:
        return error('No está en la papelera', 404)
    return jsonify({'success': True, 'message': 'Eliminado de la papelera'})


# ── enlaces públicos (sin login) ────────────────────────────────────────
@bp_extras.route('/duplicados', methods=['GET'])
def duplicados_endpoint():
    """GET /duplicados — grupos de archivos con contenido idéntico, para la
    opción 'Archivos duplicados' de Liberar espacio (detectar y revisar)."""
    usuario = usuario_actual()
    datos = nucleo.duplicados(usuario)
    datos['success'] = True
    return jsonify(datos)


@bp_extras.route('/publico-info/<token>', methods=['GET'])
def info_publico(token):
    """GET /publico-info/<token>?clave= — datos del enlace para la página
    pública (sin sesión). Si el enlace tiene clave, los detalles del archivo
    solo se entregan con la clave correcta."""
    filas = consultar("""
        SELECT propietario_id, ruta, expira_en, clave_hash, permite_descarga, puede_editar
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
        from hashlib import sha256
        clave = request.args.get('clave', '')
        if sha256(clave.encode()).hexdigest() != comp['clave_hash']:
            return jsonify({'success': True, 'requiere_clave': True,
                            'clave_valida': False}), 200
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
    })


@bp_extras.route('/publico/<token>', methods=['GET'])
def descargar_publico(token):
    """
    GET /api/nextcloud/publico/<token> — descarga por enlace público, SIN login.
    La página web /archivos/s/<token> (que sirve el frontend) apunta aquí.
    Valida token, expiración y (si tiene) clave.
    """
    filas = consultar("""
        SELECT propietario_id, ruta, expira_en, clave_hash, permite_descarga
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
        clave = request.args.get('clave', '')
        from hashlib import sha256
        if sha256(clave.encode()).hexdigest() != comp['clave_hash']:
            return error('Clave incorrecta', 401)

    try:
        fisica = ruta_fisica(comp['propietario_id'], comp['ruta'])
    except RutaInvalida:
        abort(404)
    if not os.path.isfile(fisica):
        abort(404)
    return send_file(fisica, as_attachment=True, download_name=os.path.basename(fisica))


# T-22: rutas de «Archivos del correo» (ver correo / resumen), módulo aparte
from api_correo_drive import registrar_rutas as _registrar_correo_drive
_registrar_correo_drive(bp_extras)
from api_pesados import registrar_rutas as _registrar_pesados
_registrar_pesados(bp_extras)
