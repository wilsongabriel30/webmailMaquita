# -*- coding: utf-8 -*-
"""
Formularios del Almacén — buscador de la pregunta «Colaborador» (28/09/2026)
===========================================================================
Lo que la página de responder necesita para la pregunta enlazada con nómina:

    GET /api/formulario/<token>/colaboradores?todos=1
        → {personas: [{id, nombre, cargo}]}            (la lista, una vez:
                                                         la página sugiere sola)
    GET /api/formulario/<token>/colaboradores?q=gis
        → {personas: [{id, nombre, cargo}]}            (buscar; reserva por si
                                                         la lista no carga)
    GET /api/formulario/<token>/colaboradores?id=62&p=<pregunta>
        → {persona: {id, nombre, cargo, departamento…}} (los datos al elegir)

    GET /api/almacen/encuestas/previa/colaboradores?ruta=…&q=… | &id=…&p=…
        → lo mismo, para la vista previa del editor (por la ruta del archivo)

Quién puede preguntar lo decide el AJUSTE DEL FORMULARIO (28/09/2026, pedido de
Wilson): con «Solo personas de Maquita» hace falta sesión de Raíces; sin él,
cualquiera con el enlace. Sin sesión no se entrega la lista entera: se busca
por nombre, con pocos resultados y un tope de peticiones por minuto. Solo si el
formulario tiene de verdad una pregunta «Colaborador», y al elegir se entregan
únicamente los campos que esa pregunta pide.

Cuelga sus rutas de los blueprints de los formularios: lo importa
`api_encuestas_publico` al final, antes de que se registren.

Autoría: Equipo de Tecnología Maquita — 2026-09-28
"""
import logging

from flask import jsonify, request

import api_encuestas_publico as publico
import encuestas_colaboradores as colaboradores
import encuestas_modelo as modelo
from api_encuestas import _abrir, _limpiar_definicion, bp_encuestas

log = logging.getLogger('almacen.api.encuestas.colaboradores')


# Sin sesión (formulario abierto al público) no se entrega la lista entera de
# golpe: se busca por nombre, con pocos resultados y un tope de peticiones por
# minuto. Quien responde lo nota poco; quien quisiera llevarse la nómina, mucho.
RESULTADOS_SIN_SESION = 10
PETICIONES_POR_MINUTO = 90


def _demasiadas():
    """¿Esta dirección pasó el tope del último minuto? Sin Redis, no se limita."""
    try:
        import time
        import avisos_redis
        quien = (request.headers.get('X-Real-IP')
                 or (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
                 or request.remote_addr or '?')
        clave = avisos_redis.PREFIJO + 'colab:%s:%d' % (quien, int(time.time() // 60))
        conexion = avisos_redis._conexion()
        veces = conexion.incr(clave)
        if veces == 1:
            conexion.expire(clave, 120)
        return veces > PETICIONES_POR_MINUTO
    except Exception as excepcion:
        log.debug('sin límite de peticiones: %s', excepcion)
        return False


def _atender(definicion, con_sesion, comprobar_unica=True):
    preguntas = [p for p in modelo.preguntas(definicion)
                 if p.get('tipo') == colaboradores.TIPO]
    if not preguntas:
        return publico._fallo('Este formulario no tiene ninguna pregunta de colaborador.', 404)
    if not con_sesion and _demasiadas():
        return publico._fallo('Demasiadas búsquedas seguidas. Espera un minuto.', 429)

    if request.args.get('id'):
        pregunta = next((p for p in preguntas if p['id'] == request.args.get('p')),
                        preguntas[0])
        persona = colaboradores.ficha_publica(pregunta, request.args.get('id'))
        if not persona:
            return publico._fallo('Esa persona ya no consta como activa en nómina.', 404)
        # Una sola respuesta por colaborador: se avisa al elegir, sin esperar a
        # que rellene todo y lo envíe. (En la vista previa no se comprueba.)
        ocupado = (comprobar_unica and colaboradores.unica(pregunta)
                   and colaboradores.ya_respondio(definicion['id'], pregunta['id'],
                                                  persona['id']))
        return jsonify({'success': True, 'persona': persona, 'ya_respondio': bool(ocupado)})

    if request.args.get('todos'):
        if not con_sesion:
            # La página lo entiende y pasa a buscar por nombre.
            return jsonify({'success': True, 'personas': None})
        respuesta = jsonify({'success': True, 'personas': colaboradores.lista()})
        # La lista cambia poco: el navegador la reutiliza unos minutos. Privada,
        # para que ningún intermediario la guarde.
        respuesta.headers['Cache-Control'] = 'private, max-age=300'
        return respuesta

    limite = colaboradores.LIMITE_RESULTADOS if con_sesion else RESULTADOS_SIN_SESION
    return jsonify({'success': True,
                    'personas': colaboradores.buscar(request.args.get('q') or '', limite)})


@publico.bp_encuestas_publico.route('/api/f/<token>/colaboradores', methods=['GET'])
@publico.bp_encuestas_publico.route('/api/formulario/<token>/colaboradores', methods=['GET'])
def colaboradores_de_formulario(token):
    datos, fallo = publico._cargar_publico(token)
    if fallo:
        return fallo
    fila, definicion = datos
    con_sesion = bool(publico._usuario_faro())
    # Manda el ajuste del formulario: «Solo personas de Maquita» exige sesión;
    # apagado, cualquiera con el enlace puede elegir a un colaborador.
    if fila.get('solo_internos') and not con_sesion:
        return publico._fallo('Este formulario es solo para personas de Maquita. '
                              'Inicia sesión para responderlo.', 401)
    return _atender(definicion, con_sesion)


@bp_encuestas.route('/encuestas/previa/colaboradores', methods=['GET'])
def colaboradores_de_previa():
    datos, fallo = _abrir()
    if fallo:
        return fallo
    _usuario, _ruta, definicion = datos
    return _atender(_limpiar_definicion(definicion), True, comprobar_unica=False)
