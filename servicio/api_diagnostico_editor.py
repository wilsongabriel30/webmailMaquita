# -*- coding: utf-8 -*-
"""Buzón de diagnóstico del editor de hojas — Drive Maquita (02/09/2026).

Para qué: cuando algo del editor no funciona en la pantalla de la persona, el
único sitio donde se ve por qué es su consola del navegador. Pedirla y que la
copien es lento y se pierde. Esto deja que el propio editor lo cuente aquí, y
se lee en el servidor.

Qué guarda: SOLO estado técnico —qué piezas encontró, qué respondió el editor—.
Nunca el contenido del documento. Los valores que llegan se recortan y se
escriben como texto plano, así que nada de lo que llegue se ejecuta ni se
interpreta.

Se apaga solo: pasada la fecha de `HASTA`, deja de aceptar nada.
"""
import io
import json
import logging
import os
from datetime import date, datetime

from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

bp_diag_editor = Blueprint('almacen_diag_editor', __name__)

ARCHIVO = '/home/sistemas/almacen-maquita/registros/diagnostico-editor.log'
HASTA = date(2026, 9, 30)          # después de esto, se ignora todo
TOPE_TEXTO = 400                   # por dato
TOPE_DATOS = 40                    # por envío


def _recortar(valor):
    """Un dato, en texto y corto. Nada de estructuras ni de contenido largo."""
    if isinstance(valor, (dict, list)):
        valor = json.dumps(valor, ensure_ascii=False)
    return str(valor)[:TOPE_TEXTO].replace('\n', ' ').replace('\r', ' ')


@bp_diag_editor.route('/diagnostico-editor', methods=['POST'])
def diagnostico_editor():
    if date.today() > HASTA:
        return jsonify({'success': False, 'motivo': 'cerrado'}), 200
    try:
        datos = request.get_json(silent=True) or {}
        if not isinstance(datos, dict):
            return jsonify({'success': False}), 200
        lineas = []
        cuando = datetime.now().strftime('%H:%M:%S')
        momento = _recortar(datos.get('momento') or 'sin nombre')
        for clave in list(datos.keys())[:TOPE_DATOS]:
            if clave == 'momento':
                continue
            lineas.append('%s  %-22s %-26s %s'
                          % (cuando, momento, _recortar(clave),
                             _recortar(datos[clave])))
        if not lineas:
            lineas.append('%s  %s' % (cuando, momento))
        os.makedirs(os.path.dirname(ARCHIVO), exist_ok=True)
        with io.open(ARCHIVO, 'a', encoding='utf-8') as salida:
            salida.write('\n'.join(lineas) + '\n')
    except Exception as excepcion:
        # Un fallo aquí NO puede estropearle el editor a nadie.
        log.warning('Diagnostico del editor no guardado: %s', excepcion)
    return jsonify({'success': True}), 200
