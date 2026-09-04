# -*- coding: utf-8 -*-
"""
API "superpoderes Drive" del editor OnlyOffice del Almacén.
===========================================================
Tres capacidades que replican lo que el equipo usaba en Google Drive:

  1. HISTORIAL DE VERSIONES dentro del editor (ver y restaurar sin salir):
     endpoints /onlyoffice/historial, /historial/datos, /download-version,
     /restaurar — usan las versiones que ya guarda nucleo_archivos (tabla
     `versiones` + carpeta `<uid>/versiones/`).
  2. USUARIOS para "Proteger rango" (permisos por celda/rango por-usuario) y
     menciones: /onlyoffice/usuarios — lista de la nómina con los MISMOS ids
     que usa editorConfig.user.id (str(usuario_faro)).
  3. REFERENCIAS ENTRE ARCHIVOS (estilo IMPORTRANGE): /onlyoffice/referencia —
     el editor pide los datos del libro referenciado y el DS los trae con un
     token firmado (mismo esquema JWT del módulo api_onlyoffice).

Módulo SEPARADO a propósito (política: nada de monolitos): reusa los helpers
de api_onlyoffice (firmar_jwt, tokens de descarga, key de sala estable).

Autoría: Equipo de Tecnología Maquita — 2026-07-23
"""
import hashlib
import logging
import os
import time

from flask import Blueprint, jsonify, request, send_file

import nucleo_archivos as nucleo
from almacen_bd import consultar
from api_archivos import error, usuario_actual
from api_onlyoffice import (DIAS_TOKEN, TIPOS_DOCUMENTO, _base_documento,
                            _cerrar_sesion, _nombre_usuario, _validar_peticion_ds,
                            _version_sesion, firmar_jwt, secreto_ds)
from config_almacen import URL_PUBLICA
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.oo_drive')

bp_oo_drive = Blueprint('almacen_oo_drive', __name__)


def _file_id(usuario: int, ruta: str) -> str:
    """Mismo identificador estable que usa nucleo_archivos (sha1 corto)."""
    return hashlib.sha1(f'{usuario}:{ruta}'.encode('utf-8')).hexdigest()[:16]


def _key_actual(usuario: int, ruta: str) -> str:
    """Key vigente de la sala de co-edición (idéntica a onlyoffice_config)."""
    doc_base = _base_documento(usuario, ruta)
    version = _version_sesion(doc_base)
    return hashlib.sha1(f'{doc_base}:v{version}'.encode()).hexdigest()[:20]


# ── 1. HISTORIAL DE VERSIONES EN EL EDITOR ───────────────────────────────
@bp_oo_drive.route('/onlyoffice/historial', methods=['GET'])
def oo_historial():
    """GET /onlyoffice/historial?ruta= — historial en el formato que espera
    docEditor.refreshHistory(): versiones antiguas + la versión actual."""
    usuario = usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    fid = _file_id(usuario, ruta)
    antiguas = list(reversed(nucleo.listar_versiones(usuario, fid)))  # vieja→nueva
    historia = []
    for n, v in enumerate(antiguas, start=1):
        historia.append({
            'key': f'{fid}_v{v["version_id"]}',
            'version': n,
            'created': v['creado_en'].replace('T', ' ')[:19],
            'user': {'id': str(usuario), 'name': _nombre_usuario(usuario)},
        })
    actual = len(antiguas) + 1
    historia.append({
        'key': _key_actual(usuario, ruta),
        'version': actual,
        'created': time.strftime('%Y-%m-%d %H:%M:%S'),
        'user': {'id': str(usuario), 'name': _nombre_usuario(usuario)},
    })
    return jsonify({'success': True, 'currentVersion': actual, 'history': historia,
                    'versiones': antiguas})


@bp_oo_drive.route('/onlyoffice/historial/datos', methods=['GET'])
def oo_historial_datos():
    """GET /onlyoffice/historial/datos?ruta=&version=&version_id= — datos de UNA
    versión para docEditor.setHistoryData(): url de descarga firmada + key.
    Si version_id viene vacío es la versión ACTUAL (descarga normal)."""
    usuario = usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    nombre = ruta.rsplit('/', 1)[-1]
    extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''
    version = int(request.args.get('version', 1))
    version_id = (request.args.get('version_id') or '').strip()
    exp = int(time.time()) + DIAS_TOKEN * 86400
    fid = _file_id(usuario, ruta)
    if version_id:
        token = firmar_jwt({'u': usuario, 'r': ruta, 'v': int(version_id),
                            'uso': 'descarga_version', 'exp': exp})
        url = f'{URL_PUBLICA}/api/almacen/onlyoffice/download-version?t={token}'
        key = f'{fid}_v{version_id}'
    else:
        token = firmar_jwt({'u': usuario, 'r': ruta, 'uso': 'descarga', 'exp': exp})
        url = f'{URL_PUBLICA}/api/almacen/onlyoffice/download?t={token}'
        key = _key_actual(usuario, ruta)
    datos = {'fileType': extension, 'key': key, 'url': url, 'version': version}
    datos['token'] = firmar_jwt(datos)   # el DS exige la respuesta firmada
    return jsonify(datos)


@bp_oo_drive.route('/onlyoffice/download-version', methods=['GET'])
def oo_download_version():
    """GET /onlyoffice/download-version?t= — el DS descarga el CONTENIDO de una
    versión antigua. Sin sesión: autenticado por token (uso descarga_version).
    Nota: queda exento del candado porque su ruta empieza con .../download."""
    datos = _validar_peticion_ds('descarga_version')
    if not isinstance(datos, dict):
        return datos
    try:
        usuario, ruta, vid = int(datos['u']), datos['r'], int(datos['v'])
    except (KeyError, ValueError):
        return error('Token incompleto', 400)
    fid = _file_id(usuario, ruta)
    filas = consultar("""
        SELECT version_fisico FROM versiones
        WHERE id = %s AND usuario_id = %s AND file_id = %s
    """, (vid, usuario, fid))
    if not filas:
        return error('Versión no encontrada', 404)
    fisico = os.path.join(nucleo.raiz_usuario(usuario, 'versiones'),
                          filas[0]['version_fisico'])
    if not os.path.isfile(fisico):
        return error('Contenido de la versión no disponible', 404)
    return send_file(fisico, as_attachment=True,
                     download_name=ruta.rsplit('/', 1)[-1])


@bp_oo_drive.route('/onlyoffice/restaurar', methods=['POST'])
def oo_restaurar():
    """POST /onlyoffice/restaurar?ruta= {version_id} — restaura una versión y
    CIERRA la sala de co-edición (key nueva) para que el editor recargue el
    contenido restaurado. El contenido actual queda como versión (no se pierde)."""
    usuario = usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    datos = request.get_json(silent=True) or {}
    version_id = datos.get('version_id')
    if not version_id:
        return error('version_id requerido', 400)
    # Volver atrás un archivo lo CAMBIA: mismo permiso que editarlo.
    from permisos_accion import puede_escribir, carpeta_de, MOTIVO_LECTOR
    if not puede_escribir(usuario, carpeta_de(ruta)):
        return error(MOTIVO_LECTOR, 403)
    fid = _file_id(usuario, ruta)
    try:
        nucleo.restaurar_version(usuario, fid, int(version_id))
    except FileNotFoundError:
        return error('Versión no encontrada', 404)
    _cerrar_sesion(_base_documento(usuario, ruta))   # key nueva → recarga limpia
    return jsonify({'success': True})


# ── 2. USUARIOS para "Proteger rango" y menciones ────────────────────────
@bp_oo_drive.route('/onlyoffice/usuarios', methods=['GET'])
def oo_usuarios():
    """GET /onlyoffice/usuarios — usuarios activos de la nómina con el MISMO id
    que usa el editor (str(usuario_faro)); para docEditor.setUsers()."""
    usuario_actual()
    filas = consultar("""
        SELECT u.id,
               COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre,
               COALESCE(u.email, '') AS email
        FROM usuarios u
        LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE u.active = TRUE
        ORDER BY nombre
        LIMIT 500
    """, (), nomina=True)
    usuarios = [{'id': str(f['id']), 'name': f['nombre'], 'email': f['email']}
                for f in filas]
    return jsonify({'success': True, 'usuarios': usuarios})


# ── 3. REFERENCIAS ENTRE ARCHIVOS (estilo IMPORTRANGE) ───────────────────
@bp_oo_drive.route('/onlyoffice/referencia', methods=['POST'])
def oo_referencia():
    """POST /onlyoffice/referencia — el editor pide los datos de OTRO libro
    (pegar con vínculo / fórmula externa). Cuerpo: {referenceData?, path?}.
    - referenceData.fileKey: la emitimos nosotros en el config = '<uid>|<ruta>'.
    - path: ruta del libro dentro del Almacén del MISMO usuario (fallback).
    Respuesta firmada para docEditor.setReferenceData()."""
    usuario = usuario_actual()
    ref = (request.get_json(silent=True) or {})
    file_key = ((ref.get('referenceData') or {}).get('fileKey') or '').strip()
    dueno, ruta = usuario, ''
    if file_key and '|' in file_key:
        try:
            dueno_txt, ruta = file_key.split('|', 1)
            dueno = int(dueno_txt)
        except ValueError:
            return error('Referencia inválida', 400)
    elif ref.get('path'):
        ruta = ref['path']
    if not ruta:
        return error('Falta la referencia del libro', 400)
    try:
        ruta = normalizar_ruta_virtual(ruta)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)

    # El `fileKey` lo envia el CLIENTE, asi que `dueno` es un dato no confiable.
    # Sin esta comprobacion, cualquier usuario autenticado podia pedir un enlace
    # de descarga firmado de la hoja de calculo de otra persona sabiendo su id y
    # la ruta. Se exige el mismo permiso que ya pide crear un vinculo
    # (api_vinculos.py), que es la via legitima para referenciar libros ajenos.
    from permisos_referencia import puede_referenciar
    autorizado, motivo = puede_referenciar(usuario, dueno, ruta)
    if not autorizado:
        log.warning('Referencia DENEGADA usuario=%s dueno=%s ruta=%s motivo=%s',
                    usuario, dueno, ruta, motivo)
        # Mismo mensaje que si no existiera, para no revelar que si existe.
        return error('El libro referenciado no existe', 404)

    try:
        fisica = ruta_fisica(dueno, ruta)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    if not os.path.isfile(fisica):
        return error('El libro referenciado no existe', 404)
    nombre = ruta.rsplit('/', 1)[-1]
    extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''
    if TIPOS_DOCUMENTO.get(extension) != 'cell':
        return error('Solo se puede referenciar hojas de cálculo', 400)
    exp = int(time.time()) + DIAS_TOKEN * 86400
    token_dl = firmar_jwt({'u': dueno, 'r': ruta, 'uso': 'descarga', 'exp': exp})
    datos = {
        'fileType': extension,
        'path': nombre,
        'key': _key_actual(dueno, ruta),
        'url': f'{URL_PUBLICA}/api/almacen/onlyoffice/download?t={token_dl}',
        'referenceData': {'fileKey': f'{dueno}|{ruta}', 'instanceId': URL_PUBLICA},
    }
    datos['token'] = firmar_jwt(datos)
    return jsonify(datos)
