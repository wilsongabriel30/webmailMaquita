# -*- coding: utf-8 -*-
"""
API de certificados de firma (.p12) por usuario.

Guarda los certificados del usuario EN EL SERVIDOR para que estén disponibles
desde cualquier dispositivo (PC, celular): se suben una vez y luego solo se elige
el certificado y se escribe la contraseña al firmar.

Seguridad: se guarda el .p12 tal cual (cifrado, protegido por su contraseña). La
contraseña NUNCA se almacena. Los archivos viven fuera de rutas web, en carpetas
separadas por usuario y con permisos restringidos. Cada usuario solo ve/borra los
suyos (aislados por su ID de sesión).

Rutas (se cuelgan del blueprint bp_pdf_api, prefijo /api/pdf):
  GET    /firma-digital/certificados
  POST   /firma-digital/certificados        (multipart: certificado, password)
  DELETE /firma-digital/certificados/<cid>
"""

import os
import json
import hashlib
import logging
from io import BytesIO

from flask import request, jsonify, send_file
from cryptography.x509.oid import NameOID

from .pdf_editor_api import (
    bp_pdf_api,
    requiere_autenticacion,
    obtener_usuario_id,
    dir_certificados_usuario,
    ruta_p12_guardado,
    password_guardado,
    cifrar_password_firma,
    firmar_pdf_una,
    _cargar_p12_robusto,
)

logger = logging.getLogger(__name__)

# Versión vigente de los términos/aviso de privacidad de firma electrónica.
VERSION_TERMINOS = '2026-07-23'


def _ruta_consentimiento(d):
    return os.path.join(d, 'consentimiento.json')


def _consentimiento_usuario(uid):
    d = dir_certificados_usuario(uid)
    p = _ruta_consentimiento(d)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


@bp_pdf_api.route('/firma-digital/consentimiento', methods=['GET'])
@requiere_autenticacion
def obtener_consentimiento():
    c = _consentimiento_usuario(obtener_usuario_id())
    return jsonify({
        'exito': True,
        'aceptado': bool(c and c.get('aceptado')),
        'version': (c or {}).get('version'),
        'version_actual': VERSION_TERMINOS,
    })


@bp_pdf_api.route('/firma-digital/consentimiento', methods=['POST'])
@requiere_autenticacion
def aceptar_consentimiento():
    """Registra la aceptación del aviso de privacidad / términos y condiciones."""
    from datetime import datetime, timezone, timedelta
    uid = obtener_usuario_id()
    d = dir_certificados_usuario(uid)
    tz = timezone(timedelta(hours=-5))
    reg = {
        'aceptado': True,
        'version': request.form.get('version', VERSION_TERMINOS),
        'fecha': datetime.now(tz).isoformat(),
        'ip': request.remote_addr,
        'usuario_id': uid,
    }
    with open(_ruta_consentimiento(d), 'w', encoding='utf-8') as fh:
        json.dump(reg, fh, ensure_ascii=False)
    os.chmod(_ruta_consentimiento(d), 0o600)
    return jsonify({'exito': True})


def _cert_id(nombre_archivo, tam):
    base = '%s|%s' % (nombre_archivo or 'cert.p12', tam)
    return hashlib.sha1(base.encode('utf-8')).hexdigest()[:16]


def _meta_path(d, cid):
    return os.path.join(d, os.path.basename(cid) + '.json')


def _p12_path(d, cid):
    return os.path.join(d, os.path.basename(cid) + '.p12')


@bp_pdf_api.route('/firma-digital/certificados', methods=['GET'])
@requiere_autenticacion
def listar_certificados():
    """Lista los certificados guardados del usuario (solo metadatos)."""
    uid = obtener_usuario_id()
    d = dir_certificados_usuario(uid)
    certs = []
    try:
        for f in sorted(os.listdir(d)):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(d, f), encoding='utf-8') as fh:
                        meta = json.load(fh)
                    # No se expone el token cifrado; solo si TIENE contraseña guardada
                    certs.append({
                        'id': meta.get('id'),
                        'name': meta.get('name'),
                        'nombre': meta.get('nombre'),
                        'org': meta.get('org', ''),
                        'tiene_password': bool(meta.get('pw_enc')),
                    })
                except Exception:
                    pass
    except Exception:
        logger.exception('No se pudo listar certificados del usuario %s', uid)
    return jsonify({'exito': True, 'datos': certs})


@bp_pdf_api.route('/firma-digital/certificados', methods=['POST'])
@requiere_autenticacion
def guardar_certificado():
    """Verifica el .p12 con su contraseña y lo guarda para el usuario."""
    uid = obtener_usuario_id()
    # Requiere haber aceptado el aviso de privacidad / términos y condiciones
    if not _consentimiento_usuario(uid):
        return jsonify({'exito': False, 'codigo': 'SIN_CONSENTIMIENTO',
                        'mensaje': 'Debes aceptar el aviso de privacidad para guardar el certificado.'}), 403
    archivo = request.files.get('certificado')
    password = request.form.get('password', '')
    if not archivo:
        return jsonify({'exito': False, 'mensaje': 'Se requiere el certificado .p12'}), 400

    data = archivo.read()
    # Verificar que abre con la contraseña y extraer nombre/organización
    try:
        _clave, cert, _cadena, _conv = _cargar_p12_robusto(data, password)
    except ValueError as e:
        return jsonify({'exito': False, 'mensaje': str(e)}), 400
    if not cert:
        return jsonify({'exito': False, 'mensaje': 'El .p12 no contiene un certificado válido'}), 400

    try:
        nombre = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    except Exception:
        nombre = 'Sin nombre'
    try:
        org = cert.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value
    except Exception:
        org = ''

    d = dir_certificados_usuario(uid)
    cid = _cert_id(archivo.filename, len(data))
    ruta = _p12_path(d, cid)
    with open(ruta, 'wb') as fh:
        fh.write(data)
    os.chmod(ruta, 0o600)

    meta = {
        'id': cid,
        'name': archivo.filename or 'certificado.p12',
        'nombre': nombre,
        'org': org,
    }
    # Guardar la contraseña CIFRADA solo si el usuario lo eligió
    guardar_pw = request.form.get('guardar_password', 'false').lower() in ('1', 'true', 'si', 'sí', 'on')
    if guardar_pw:
        meta['pw_enc'] = cifrar_password_firma(password)
    with open(_meta_path(d, cid), 'w', encoding='utf-8') as fh:
        json.dump(meta, fh, ensure_ascii=False)
    os.chmod(_meta_path(d, cid), 0o600)
    return jsonify({'exito': True, 'datos': {
        'id': cid, 'name': meta['name'], 'nombre': nombre, 'org': org,
        'tiene_password': bool(guardar_pw),
    }})


@bp_pdf_api.route('/firma-digital/firmar-multiple', methods=['POST'])
@requiere_autenticacion
def firmar_multiple():
    """
    Aplica VARIAS firmas en un mismo documento en una sola operación (firma
    múltiple): en muchas páginas o varias veces, con uno o varios certificados,
    sin descargar/re-subir entre firma y firma.

    multipart/form-data:
      - archivo: PDF a firmar
      - firmas: JSON [{certificado_id, pagina, x, y, ancho, alto}, ...]
      - passwords: JSON {certificado_id: password, ...}
    """
    uid = obtener_usuario_id()
    archivo_pdf = request.files.get('archivo')
    try:
        firmas = json.loads(request.form.get('firmas', '[]'))
        passwords = json.loads(request.form.get('passwords', '{}'))
    except Exception:
        return jsonify({'exito': False, 'mensaje': 'Datos de firmas inválidos'}), 400
    if not archivo_pdf:
        return jsonify({'exito': False, 'mensaje': 'Se requiere el PDF'}), 400
    if not firmas:
        return jsonify({'exito': False, 'mensaje': 'No hay firmas para aplicar'}), 400

    pdf_bytes = archivo_pdf.read()
    for i, fma in enumerate(firmas):
        cid = fma.get('certificado_id')
        ruta = ruta_p12_guardado(uid, cid)
        if not ruta:
            return jsonify({'exito': False,
                            'mensaje': 'Certificado no encontrado (%s)' % cid}), 404
        pw = passwords.get(cid) or password_guardado(uid, cid) or ''
        try:
            pdf_bytes = firmar_pdf_una(
                pdf_bytes, ruta, pw,
                'Documento firmado digitalmente', 'Ecuador',
                int(fma.get('pagina', 0)),
                float(fma.get('x', 50)), float(fma.get('y', 50)),
                float(fma.get('ancho', 200)), float(fma.get('alto', 70)))
        except ValueError as e:
            return jsonify({'exito': False,
                            'mensaje': 'Firma %d: %s' % (i + 1, str(e))}), 400
        except Exception as e:
            logger.exception('Error en firma múltiple (firma %d)', i + 1)
            return jsonify({'exito': False,
                            'mensaje': 'Error al firmar (firma %d): %s' % (i + 1, str(e))}), 400

    return send_file(BytesIO(pdf_bytes), mimetype='application/pdf',
                     as_attachment=True, download_name='documento_firmado.pdf')


def _leer_meta(d, cid):
    p = _meta_path(d, cid)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


def _guardar_meta(d, cid, meta):
    with open(_meta_path(d, cid), 'w', encoding='utf-8') as fh:
        json.dump(meta, fh, ensure_ascii=False)
    os.chmod(_meta_path(d, cid), 0o600)


@bp_pdf_api.route('/firma-digital/certificados/<cid>/password', methods=['POST'])
@requiere_autenticacion
def recordar_password_certificado(cid):
    """Guarda (cifrada) la contraseña de un certificado ya almacenado.
    Elección del usuario: si la activa, no se le vuelve a pedir al firmar."""
    uid = obtener_usuario_id()
    if not _consentimiento_usuario(uid):
        return jsonify({'exito': False, 'codigo': 'SIN_CONSENTIMIENTO',
                        'mensaje': 'Debes aceptar el aviso de privacidad.'}), 403
    d = dir_certificados_usuario(uid)
    meta = _leer_meta(d, cid)
    ruta = ruta_p12_guardado(uid, cid)
    if not meta or not ruta:
        return jsonify({'exito': False, 'mensaje': 'Certificado no encontrado'}), 404
    password = request.form.get('password', '')
    with open(ruta, 'rb') as fh:
        data = fh.read()
    try:
        _cargar_p12_robusto(data, password)   # valida la contraseña
    except ValueError as e:
        return jsonify({'exito': False, 'mensaje': str(e)}), 400
    meta['pw_enc'] = cifrar_password_firma(password)
    _guardar_meta(d, cid, meta)
    return jsonify({'exito': True, 'tiene_password': True})


@bp_pdf_api.route('/firma-digital/certificados/<cid>/password', methods=['DELETE'])
@requiere_autenticacion
def olvidar_password_certificado(cid):
    """Olvida la contraseña guardada: a partir de ahora se pedirá al firmar
    (el .p12 sigue almacenado)."""
    uid = obtener_usuario_id()
    d = dir_certificados_usuario(uid)
    meta = _leer_meta(d, cid)
    if not meta:
        return jsonify({'exito': False}), 404
    meta.pop('pw_enc', None)
    _guardar_meta(d, cid, meta)
    return jsonify({'exito': True, 'tiene_password': False})


@bp_pdf_api.route('/firma-digital/certificados/<cid>', methods=['DELETE'])
@requiere_autenticacion
def eliminar_certificado(cid):
    """Elimina un certificado guardado del usuario."""
    uid = obtener_usuario_id()
    d = dir_certificados_usuario(uid)
    borrado = False
    for p in (_p12_path(d, cid), _meta_path(d, cid)):
        if os.path.exists(p):
            try:
                os.remove(p)
                borrado = True
            except Exception:
                logger.exception('No se pudo borrar %s', p)
    return jsonify({'exito': borrado})
