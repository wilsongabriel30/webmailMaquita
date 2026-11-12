# -*- coding: utf-8 -*-
"""
Aviso a Tecnología cuando el editor no puede abrir un archivo (20/10/2026).
==========================================================================
La página del editor (editor_onlyoffice.html) recibe los errores del Document
Server en `onError` (p. ej. errorCode -4: no pudo descargar el archivo). Hasta hoy
solo se mostraban en pantalla y Tecnología se enteraba cuando la persona
reclamaba. Ahora la página los manda aquí y sale un correo a Tecnología
con usuario, ruta, tamaño y el error (limites_editor.avisar_tecnologia, uno por
asunto cada 30 min).

Cuelga sus rutas de bp_onlyoffice (api_onlyoffice): basta con importar este
módulo antes de registrar el blueprint (integracion_faro).
Autoría: Equipo de Tecnología Maquita — 2026-10-20
"""
import logging
import os

from flask import jsonify, request

import limites_editor
from api_archivos import usuario_actual
from api_onlyoffice import bp_onlyoffice
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.editor_errores')


@bp_onlyoffice.route('/onlyoffice/error-editor', methods=['POST'])
def error_editor():
    """POST {ruta, error} desde la página del editor. Siempre responde OK: avisar
    no puede fallar más que el propio editor."""
    usuario = usuario_actual()
    datos = request.get_json(silent=True) or {}
    ruta = str(datos.get('ruta') or '')[:400]
    detalle_error = str(datos.get('error') or '')[:600]
    tamano = 'desconocido'
    try:
        fisica = ruta_fisica(usuario, normalizar_ruta_virtual(ruta))
        if os.path.isfile(fisica):
            tamano = limites_editor.humano(os.path.getsize(fisica))
    except (RutaInvalida, OSError, ValueError):
        pass
    limites_editor.avisar_tecnologia(
        'El editor no pudo abrir un archivo',
        'Usuario %s · archivo %s · tamaño %s · error del editor: %s'
        % (usuario, ruta or '(sin ruta)', tamano, detalle_error or '(sin detalle)'))
    return jsonify({'success': True})
