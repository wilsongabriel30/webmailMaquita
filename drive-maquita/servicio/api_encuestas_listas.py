"""
Formularios del Almacén — sugerencias de la pregunta «Lista desde archivo» (10/11/2026)
=====================================================================================
    GET /api/formulario/<token>/lista?p=<pregunta>&q=<texto>&padres=<json>
        → {opciones: [...], completo: bool}
          `padres` = {nombre_pregunta: valor} de las preguntas que filtran la
          lista (la cascada). Nunca se entrega el archivo entero.

    GET /api/almacen/encuestas/previa/lista?ruta=…&p=…&q=…&padres=…
        → lo mismo, para la vista previa del editor

    GET /api/almacen/encuestas/lista/columnas?ruta=<.forma>&archivo=<csv o xlsx>
        → {columnas, filas, muestra}: para elegir columna y filtros en el editor

Cuelga sus rutas de los blueprints de los formularios: lo importa
`api_encuestas_publico` al final, como el buscador de colaboradores.

Autoría: Equipo de Tecnología Maquita — 2026-11-10
"""
import json
import logging

from flask import jsonify, request

import api_encuestas_publico as publico
import encuestas_listas as listas
import encuestas_modelo as modelo
from api_encuestas import _abrir, _limpiar_definicion, bp_encuestas

log = logging.getLogger('almacen.api.encuestas.listas')


def _padres():
    try:
        datos = json.loads(request.args.get('padres') or '{}')
    except ValueError:
        return {}
    if not isinstance(datos, dict):
        return {}
    return {str(k)[:64]: (str(v)[:300] if v is not None else None) for k, v in list(datos.items())[:10]}


def _atender(definicion, propietario):
    pid = request.args.get('p') or ''
    pregunta = next((p for p in modelo.preguntas(definicion)
                     if p['id'] == pid and p.get('tipo') == 'lista'), None)
    if not pregunta:
        return publico._fallo('Esa pregunta no es una lista.', 404)
    try:
        opciones, completo = listas.opciones(pregunta, propietario, _padres(),
                                             (request.args.get('q') or '')[:100])
    except listas.ListaNoDisponible as e:
        return publico._fallo(str(e), 409)
    return jsonify({'success': True, 'opciones': opciones, 'completo': completo})


@publico.bp_encuestas_publico.route('/api/f/<token>/lista', methods=['GET'])
@publico.bp_encuestas_publico.route('/api/formulario/<token>/lista', methods=['GET'])
def lista_de_formulario(token):
    datos, fallo = publico._cargar_publico(token)
    if fallo:
        return fallo
    fila, definicion = datos
    if fila.get('solo_internos') and not publico._usuario_faro():
        return publico._fallo('Este formulario es solo para personas de Maquita. '
                              'Inicia sesión para responderlo.', 401)
    try:
        from api_encuestas_colaboradores import _demasiadas
        if _demasiadas():
            return publico._fallo('Demasiadas búsquedas seguidas. Espera un minuto.', 429)
    except ImportError:
        pass
    return _atender(definicion, fila['propietario'])


@bp_encuestas.route('/encuestas/previa/lista', methods=['GET'])
def lista_de_previa():
    datos, fallo = _abrir()
    if fallo:
        return fallo
    usuario, _ruta, definicion = datos
    return _atender(_limpiar_definicion(definicion), usuario)


@bp_encuestas.route('/encuestas/lista/columnas', methods=['GET'])
def columnas_de_archivo():
    datos, fallo = _abrir()
    if fallo:
        return fallo
    usuario, _ruta, _definicion = datos
    archivo = (request.args.get('archivo') or '').strip()
    if not archivo.lower().endswith(listas.EXTENSIONES) or '..' in archivo:
        return publico._fallo('Elige un archivo .csv o .xlsx de tu Drive.', 400)
    try:
        cargado = listas.cargar(listas._fisica(usuario, archivo))
    except listas.ListaNoDisponible as e:
        return publico._fallo(str(e), 404)
    except Exception as e:                       # archivo dañado o con otro formato
        log.warning('lista %s: %s', archivo, e)
        return publico._fallo('No se pudo leer el archivo. Guárdalo como CSV (UTF-8) o Excel (.xlsx).', 400)
    return jsonify({'success': True, 'columnas': cargado['columnas'],
                    'filas': len(cargado['filas']), 'muestra': cargado['filas'][:3]})
