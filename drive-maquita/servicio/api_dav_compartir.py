# -*- coding: utf-8 -*-
"""
Compartir por enlace desde la app de Windows (autenticado por token DAV).
=========================================================================
QUÉ: endpoint `POST /api/almacen/dav/compartir` que crea un enlace público de
un archivo del usuario y devuelve la URL lista para pegar. Lo llama la app de
Windows con «clic derecho → Compartir con Drive Maquita», SIN que la persona
entre a la web (P-12).

CÓMO AUTENTICA: HTTP Basic, igual que el WebDAV — usuario = ID de FARO,
contraseña = el token del equipo (el mismo con el que monta el disco). No usa
sesión ni CSRF; su seguridad es el token. Por eso este endpoint está exento del
«candado» de sesión de /api/almacen (ver integracion_faro.py), igual que las
rutas de OnlyOffice, cuya seguridad es su propio token.

REUTILIZA la lógica de compartir: llama a `crear_compartido()` de api_compartir
(misma política de macros, misma tabla, mismos enlaces). Aquí NO se duplica esa
lógica; solo se resuelve el usuario por token y se fuerza «enlace público».

Backend: api_compartir.crear_compartido | Doc: PENDIENTES-BACKEND.md (P-12)
Autoría: Equipo de Tecnología Maquita — 2026-08-04
"""
import logging

from flask import Blueprint, jsonify, request

from api_compartir import crear_compartido
from dav_auth import usuario_por_token as _usuario_por_token

log = logging.getLogger('almacen.dav_compartir')

bp_dav_compartir = Blueprint('almacen_dav_compartir', __name__)


@bp_dav_compartir.route('/dav/compartir', methods=['POST'])
def compartir_por_token():
    """POST /api/almacen/dav/compartir
    Auth: Basic (usuario = ID FARO, contraseña = token del equipo).
    Body: { "ruta": "/CARPETA/archivo.xlsx", "publico": true,
            "expira_dias"?: int, "clave"?: str }
    OK:   { "success": true, "url": "https://drive.maquita.com.ec/s/..." }
    """
    usuario_id = _usuario_por_token(request.authorization)
    if usuario_id is None:
        # 401 → la app pedirá reconectar el equipo (token caducado/revocado).
        return jsonify({'success': False,
                        'error': 'No se pudo autenticar el equipo. Vuelve a '
                                 'conectar el Drive e inténtalo otra vez.'}), 401

    body = request.get_json(silent=True) or {}
    ruta = (body.get('ruta') or '').strip()
    if not ruta:
        return jsonify({'success': False,
                        'error': 'Falta indicar el archivo a compartir.'}), 400

    # P-13: la app manda CÓMO debe abrirse el enlace. `modo` lo valida y aplica
    # crear_compartido (descargar | ver | editar); si no viene, «descargar».
    # `permiso` ('escritura'|'lectura') es el rol del invitado; «editar» ya
    # implica escritura, pero se respeta si lo mandan explícito.
    modo = (body.get('modo') or 'descargar').strip().lower()
    permiso = (body.get('permiso') or '').strip().lower()
    rol = 'editor' if (permiso == 'escritura' or modo == 'editar') else 'lector'

    # Las validaciones reales (ruta válida, política de macros, permisos de
    # unidad) las hace crear_compartido, que es el mismo núcleo que usa la web.
    datos = {
        'ruta': ruta,
        'tipo': 3,                 # enlace público
        'permisos': 3 if rol == 'editor' else 1,
        'rol': rol,
        'modo': modo,
        'permite_descarga': body.get('permite_descarga', True) is not False,
        'expira_dias': body.get('expira_dias'),
        'clave': body.get('clave'),
    }
    resp, status = crear_compartido(usuario_id, datos)
    if status == 201:
        comp = (resp.get_json() or {}).get('compartido', {})
        log.info('Enlace público por token: usuario=%s ruta=%s modo=%s',
                 usuario_id, ruta, comp.get('modo'))
        return jsonify({'success': True,
                        'url': comp.get('url'),
                        'modo': comp.get('modo'),
                        'puede_editar': comp.get('puede_editar'),
                        'token': comp.get('token')})
    # Error legible ya formateado por crear_compartido (macros, ruta, etc.).
    return resp, status
