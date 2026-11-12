"""
Formularios del Almacén — importar un Excel de ODK o Kobo (XLSForm) en el editor (10/11/2026)
==============================================================================================
    POST /api/almacen/encuestas/importar-xlsform?ruta=…   (multipart: archivo)

Convierte el XLSForm con `encuestas_importar_xlsform` y devuelve los elementos
YA LIMPIOS (pasan por `encuestas_modelo.limpiar`, igual que al guardar) más el
informe de lo que hay que revisar. No guarda nada: el editor los coloca y los
guarda con su autoguardado de siempre, así que se puede deshacer.

Los nombres de variable no chocan con los que ya tiene el formulario abierto.
Lo importa `api_encuestas_publico` al final, como los demás complementos.

Autoría: Equipo de Tecnología Maquita — 2026-11-10
"""
import logging

from flask import jsonify, request

import encuestas_importar_xlsform as importador
import encuestas_modelo as modelo
from encuestas_modelo_reglas import ReglasInvalidas
from encuestas_xlsform_leer import XLSFormInvalido
from api_encuestas import _abrir, _limpiar_definicion, bp_encuestas, error

log = logging.getLogger('almacen.api.encuestas.importar_xlsform')


@bp_encuestas.route('/encuestas/importar-xlsform', methods=['POST'])
def importar_xlsform():
    datos, fallo = _abrir(escritura=True)
    if fallo:
        return fallo
    _usuario, ruta, definicion = datos
    archivo = request.files.get('archivo')
    if archivo is None:
        return error('No se recibió ningún archivo.', 400)
    if not (archivo.filename or '').lower().endswith(('.xlsx', '.xlsm')):
        return error('El archivo tiene que ser un Excel .xlsx (el XLSForm de ODK o Kobo).', 400)
    actual = _limpiar_definicion(definicion)
    ocupados = {p.get('nombre') for p in modelo.preguntas(actual) if p.get('nombre')}
    try:
        bruto, informe = importador.importar(archivo.read(importador.leer_mod.TAMANO_MAX + 1), ocupados)
        limpio = modelo.limpiar(bruto)
    except (XLSFormInvalido, ReglasInvalidas, ValueError) as e:
        return error(str(e), 400)
    except Exception as e:                       # un Excel raro no debe tumbar nada
        log.exception('importando XLSForm en %s: %s', ruta, e)
        return error('No se pudo leer ese Excel como XLSForm.', 400)
    log.info('XLSForm importado en %s: %s preguntas, %s avisos', ruta, informe['preguntas'],
             informe['avisos_total'])
    return jsonify({'success': True, 'titulo': limpio['titulo'], 'elementos': limpio['elementos'],
                    'informe': informe})
