# -*- coding: utf-8 -*-
"""Telemetría de las sesiones del editor de documentos — Drive Maquita (25/11/2026).

Para qué: el Document Server cierra la sala de edición cuando la persona se queda
sola y desconectada (inactividad de 1 h, equipo suspendido, corte de red). Al
volver, el editor pedía «La versión ha cambiado» y recargaba la página entera; lo
que se escribía en ese momento se perdía. Desde el 25/11/2026 la página atiende
`onRequestRefreshFile` y recarga el documento en su sitio con la clave nueva.

Este buzón deja constancia de cada refresco (pedido, hecho, fallido) y de los
errores del editor, con usuario, archivo y hora, para comprobar en el servidor
que el arreglo funciona sin tener que pedir capturas a nadie.

Qué guarda: SOLO estado técnico. Nunca el contenido del documento. Los valores se
recortan y se escriben como texto plano en una línea.
"""
import io
import json
import logging
import os
from datetime import datetime

from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

bp_telemetria_editor = Blueprint('almacen_telemetria_editor', __name__)

ARCHIVO = '/home/sistemas/almacen-maquita/registros/telemetria-editor.log'
EVENTOS = {'refresco_pedido', 'refresco_hecho', 'refresco_fallido', 'error_editor'}
TOPE_TEXTO = 300


def _texto(valor) -> str:
    if isinstance(valor, (dict, list)):
        valor = json.dumps(valor, ensure_ascii=False)
    return str(valor if valor is not None else '-')[:TOPE_TEXTO].replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')


def _usuario() -> str:
    """Id del usuario de la sesión web; «publico» si entra por enlace."""
    try:
        from api_archivos import usuario_actual
        return str(usuario_actual())
    except Exception:
        return 'publico'


@bp_telemetria_editor.route('/telemetria-editor', methods=['POST'])
def telemetria_editor():
    try:
        datos = request.get_json(silent=True) or {}
        if not isinstance(datos, dict) or datos.get('evento') not in EVENTOS:
            return jsonify({'success': False}), 200
        linea = '\t'.join([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            _usuario(),
            request.headers.get('X-Real-IP') or request.remote_addr or '-',
            _texto(datos.get('evento')),
            _texto(datos.get('ruta')),
            _texto(datos.get('clave_vieja')),
            _texto(datos.get('clave_nueva')),
            _texto(datos.get('detalle')),
        ])
        os.makedirs(os.path.dirname(ARCHIVO), exist_ok=True)
        with io.open(ARCHIVO, 'a', encoding='utf-8') as salida:
            salida.write(linea + '\n')
    except Exception as excepcion:
        # Un fallo aquí NO puede estropearle el editor a nadie.
        log.warning('Telemetría del editor no guardada: %s', excepcion)
    return jsonify({'success': True}), 200
