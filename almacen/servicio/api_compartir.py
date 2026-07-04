# -*- coding: utf-8 -*-
"""
API de compartir del Almacén Maquita.
=====================================
Compartir con personas o por enlace público (semántica Google Drive),
listado de compartidos y búsqueda de usuarios para el autocompletado.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import logging
import secrets

from flask import Blueprint, jsonify, request

from almacen_bd import consultar, ejecutar
from api_archivos import error, usuario_actual
from config_almacen import URL_PUBLICA
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual

log = logging.getLogger('almacen.compartir')

bp_compartir = Blueprint('almacen_compartir', __name__)

TIPO_USUARIO, TIPO_GRUPO, TIPO_ENLACE = 0, 1, 3


@bp_compartir.route('/compartir', methods=['POST'])
def compartir():
    """
    POST /compartir — {ruta, tipo, permisos, con_quien?, clave?, expira?}
    tipo: 0=usuario, 1=grupo, 3=enlace público. Contrato: HTTP 201.
    """
    usuario = usuario_actual()
    datos = request.get_json() or {}
    try:
        ruta = normalizar_ruta_virtual(datos.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    if ruta == '/':
        return error('No se puede compartir la raíz', 400)

    tipo = int(datos.get('tipo', TIPO_ENLACE))
    permisos = int(datos.get('permisos', 1))
    destinatario = (datos.get('con_quien') or datos.get('shareWith') or '').strip() or None
    if tipo in (TIPO_USUARIO, TIPO_GRUPO) and not destinatario:
        return error('Falta el destinatario', 400)

    token = secrets.token_urlsafe(24) if tipo == TIPO_ENLACE else None

    # Expiración (días desde hoy) y clave opcional — como los enlaces de Drive de pago.
    import hashlib
    from datetime import datetime, timezone, timedelta
    expira_en = None
    try:
        dias = int(datos.get('expira_dias') or 0)
        if dias > 0:
            expira_en = datetime.now(timezone.utc) + timedelta(days=dias)
    except (TypeError, ValueError):
        expira_en = None
    clave = (datos.get('clave') or '').strip()
    clave_hash = hashlib.sha256(clave.encode()).hexdigest() if clave else None
    # ¿Se permite descargar/copiar? (control tipo Drive; por defecto sí)
    permite_descarga = datos.get('permite_descarga', True) is not False

    # Compartir con una PERSONA por correo (interno o externo) con rol lector/editor.
    # Genera SIEMPRE un token (el enlace es la credencial de acceso; puede llevar clave).
    email = (datos.get('email') or '').strip().lower()[:255] or None
    rol = (datos.get('rol') or '').strip()   # 'lector' | 'editor'
    puede_editar = (rol == 'editor')
    if email:
        import re as _re
        if not _re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
            return error('Correo inválido', 400)
        if token is None:
            token = secrets.token_urlsafe(24)

    fila = ejecutar("""
        INSERT INTO compartidos (propietario_id, ruta, tipo, destinatario, token, permisos,
                                 expira_en, clave_hash, permite_descarga, email, puede_editar)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, creado_en
    """, (usuario, ruta, tipo, destinatario, token, permisos,
          expira_en, clave_hash, permite_descarga, email, puede_editar))

    compartido = {
        'id': fila['id'],
        'ruta': ruta,
        'tipo': tipo,
        'permisos': permisos,
        'con_quien': destinatario or email,
        'email': email,
        'rol': rol or ('editor' if permisos & 2 else 'lector'),
        'puede_editar': puede_editar,
        'token': token,
        'url': f'{URL_PUBLICA}/almacen-s/{token}' if token else None,
        'expira_en': expira_en.isoformat() if expira_en else None,
        'con_clave': bool(clave_hash),
        'permite_descarga': permite_descarga,
        'creado_en': fila['creado_en'].isoformat(),
    }
    log.info('Compartido id=%s ruta=%s tipo=%s por usuario %s',
             fila['id'], ruta, tipo, usuario)
    return jsonify({'success': True, 'compartido': compartido}), 201


@bp_compartir.route('/shares', methods=['GET'])
@bp_compartir.route('/compartidos', methods=['GET'])
def listar_compartidos():
    """GET /compartidos — lo que YO he compartido (ambas rutas del contrato)."""
    usuario = usuario_actual()
    filas = consultar("""
        SELECT id, ruta, tipo, destinatario AS con_quien, token, permisos, creado_en
        FROM compartidos WHERE propietario_id = %s ORDER BY creado_en DESC
    """, (usuario,))
    compartidos = []
    for fila in filas:
        fila = dict(fila)
        fila['creado_en'] = fila['creado_en'].isoformat()
        fila['url'] = f"{URL_PUBLICA}/almacen-s/{fila['token']}" if fila['token'] else None
        compartidos.append(fila)
    return jsonify({'success': True, 'compartidos': compartidos,
                    'total': len(compartidos)})


@bp_compartir.route('/compartidos/<int:compartido_id>', methods=['DELETE'])
def eliminar_compartido(compartido_id):
    """DELETE /compartidos/<id> — deja de compartir (solo el propietario)."""
    usuario = usuario_actual()
    fila = ejecutar("""
        DELETE FROM compartidos WHERE id = %s AND propietario_id = %s RETURNING id
    """, (compartido_id, usuario))
    if not fila:
        return error('Compartido no encontrado', 404)
    return jsonify({'success': True, 'message': 'Se dejó de compartir'})


@bp_compartir.route('/usuarios/buscar', methods=['GET'])
def buscar_usuarios():
    """
    GET /usuarios/buscar?q= — autocompletado para compartir.
    Contrato: {usuarios: [{id, nombre, email, tipo}], grupos, total}.
    Lee de la base de nómina (solo lectura): son los mismos usuarios de FARO.
    """
    usuario_actual()
    consulta = (request.args.get('q') or '').strip()
    limite = min(int(request.args.get('limite', 10)), 25)
    if len(consulta) < 2:
        return jsonify({'success': True, 'usuarios': [], 'grupos': [], 'total': 0})

    filas = consultar("""
        SELECT u.username AS id,
               COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre,
               COALESCE(u.email, '') AS email
        FROM usuarios u
        LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE u.active = TRUE
          AND (LOWER(u.username) LIKE LOWER(%s) || '%%'
               OR LOWER(COALESCE(t.nombres, '')) LIKE LOWER(%s) || '%%'
               OR LOWER(COALESCE(t.apellidos, '')) LIKE LOWER(%s) || '%%')
        ORDER BY u.username
        LIMIT %s
    """, (consulta, consulta, consulta, limite), nomina=True)

    usuarios = [{'id': f['id'], 'nombre': f['nombre'], 'email': f['email'],
                 'tipo': 'usuario'} for f in filas]
    return jsonify({'success': True, 'usuarios': usuarios, 'grupos': [],
                    'total': len(usuarios)})
