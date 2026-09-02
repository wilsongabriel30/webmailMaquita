# -*- coding: utf-8 -*-
"""
Formularios del Almacén — modo cuestionario: endpoints de corrección

Va aparte de `api_encuestas` por la regla de no engordar módulos: aquel ya
rondaba las 700 líneas y esto es una responsabilidad distinta —corregir— con su
propio ciclo de vida.

Comparte el blueprint `bp_encuestas`, así que las rutas siguen colgando de
`/api/almacen/encuestas/...` y no hay que registrar nada nuevo.

    POST /api/almacen/encuestas/calificar?ruta=    → puntos a mano
    POST /api/almacen/encuestas/recalificar?ruta=  → rehace todas las notas

Autoría: Equipo de Tecnología Maquita — 2026-08-25
"""
from flask import jsonify, request

import encuestas_bd as ebd
import encuestas_calificar as calificar
import encuestas_modelo as modelo
from api_archivos import error
from api_encuestas import (_abrir, _limpiar_definicion, _sincronizar_bd,
                           bp_encuestas)


@bp_encuestas.route('/encuestas/calificar', methods=['POST'])
def calificar_respuesta():
    """Pone a mano los puntos de una respuesta (modo cuestionario).

    Es lo que cierra el ciclo de las preguntas que el sistema no puede
    calificar solo —párrafo, escala, fecha, hora—: quedan «pendientes» y aquí
    una persona les da los puntos que correspondan.
    """
    datos, fallo = _abrir(escritura=True)
    if fallo:
        return fallo
    usuario, ruta, definicion = datos
    definicion = _limpiar_definicion(definicion)
    _sincronizar_bd(usuario, ruta, definicion)

    cuerpo = request.get_json(silent=True) or {}
    try:
        respuesta_id = int(cuerpo.get('id'))
    except (TypeError, ValueError):
        return error('Falta indicar la respuesta', 400)

    fila = ebd.respuesta(definicion['id'], respuesta_id)
    if not fila:
        return error('Esa respuesta ya no existe', 404)

    calificacion = fila.get('calificacion') or calificar.calificar(
        definicion, fila.get('datos') or {})
    detalle = calificacion.get('detalle') or {}

    puestos = cuerpo.get('puntos')
    if not isinstance(puestos, dict):
        return error('No se recibieron puntos', 400)

    posibles = {p['id']: (p.get('clave') or {}).get('puntos') or 0
                for p in modelo.preguntas(definicion)}

    for pregunta_id, valor in puestos.items():
        if pregunta_id not in detalle:
            continue
        try:
            dados = float(valor)
        except (TypeError, ValueError):
            return error('Puntuación no válida', 400)
        # No se pueden dar más puntos de los que vale la pregunta: la nota
        # dejaría de significar nada frente al total.
        tope = float(posibles.get(pregunta_id) or 0)
        dados = max(0.0, min(dados, tope))
        detalle[pregunta_id]['puntos'] = (int(dados) if dados == int(dados)
                                          else round(dados, 2))
        detalle[pregunta_id]['estado'] = 'revisada'

    calificacion['detalle'] = detalle
    calificacion['puntos'] = sum(d.get('puntos') or 0 for d in detalle.values())
    if calificacion['puntos'] == int(calificacion['puntos']):
        calificacion['puntos'] = int(calificacion['puntos'])
    calificacion['pendientes'] = sum(
        1 for d in detalle.values() if d.get('estado') == 'pendiente')

    ebd.guardar_calificacion(respuesta_id, calificacion,
                             revisada=calificacion['pendientes'] == 0)
    return jsonify({'success': True, 'calificacion': calificacion})


@bp_encuestas.route('/encuestas/recalificar', methods=['POST'])
def recalificar():
    """Vuelve a calificar TODAS las respuestas con la clave actual.

    Hace falta cuando se corrige la clave después de haber recibido entregas:
    las notas ya guardadas se calcularon con la clave vieja. No se hace solo al
    editar la clave porque borraría las correcciones puestas a mano.
    """
    datos, fallo = _abrir(escritura=True)
    if fallo:
        return fallo
    usuario, ruta, definicion = datos
    definicion = _limpiar_definicion(definicion)
    _sincronizar_bd(usuario, ruta, definicion)

    cambiadas = 0
    for fila in ebd.listar_respuestas(definicion['id']):
        nueva = calificar.calificar(definicion, fila.get('datos') or {})
        # Lo corregido a mano se respeta: se recalcula lo automático y se
        # conservan los puntos que puso una persona.
        viejo = (fila.get('calificacion') or {}).get('detalle') or {}
        for pregunta_id, dato in (nueva.get('detalle') or {}).items():
            anterior = viejo.get(pregunta_id) or {}
            if anterior.get('estado') == 'revisada':
                nueva['detalle'][pregunta_id] = anterior
        nueva['puntos'] = sum(d.get('puntos') or 0
                              for d in nueva['detalle'].values())
        if nueva['puntos'] == int(nueva['puntos']):
            nueva['puntos'] = int(nueva['puntos'])
        nueva['pendientes'] = sum(1 for d in nueva['detalle'].values()
                                  if d.get('estado') == 'pendiente')
        ebd.guardar_calificacion(fila['id'], nueva,
                                 revisada=nueva['pendientes'] == 0)
        cambiadas += 1

    return jsonify({'success': True, 'respuestas': cambiadas})
