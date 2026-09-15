"""Formularios del Almacén — vista previa interactiva del editor.

La vista previa pintaba las preguntas desactivadas en una sola lista: no
seguía los saltos de sección ni validaba, así que los condicionales solo se
podían probar publicando el formulario (10/09/2026).

Ahora el editor abre la MISMA página de responder en modo vista previa. Lo que
esa página necesita y no puede pedir por el token vive aquí:

  GET  /archivos-almacen/formulario-previa?ruta=…    → la página
  GET  /api/almacen/encuestas/previa?ruta=…          → la definición
  POST /api/almacen/encuestas/previa/validar?ruta=…  → validar sin guardar

Todo con la sesión y los permisos del ARCHIVO, como el propio editor: sirve
aunque el formulario no esté publicado, esté cerrado o fuera de plazo.

Cuelga sus rutas de los blueprints de `api_encuestas`: basta con importarlo
antes de registrarlos (lo hace `integracion_faro.py`), igual que
`api_encuestas_quiz.py`.
"""
from flask import jsonify, request

import api_encuestas_publico as publico
import encuestas_ajustes as ajustes_mod
import encuestas_correo as correo_mod
from api_archivos import error
from api_encuestas import (_abrir, _limpiar_definicion, _pagina,
                           _sincronizar_bd, bp_encuestas, bp_encuestas_web)


@bp_encuestas_web.route('/archivos-almacen/formulario-previa')
def pagina_previa():
    """La página de responder, en modo vista previa (bajo el candado)."""
    return _pagina('encuesta_publica.html')


def _preparar():
    """(usuario, definicion limpia, fila) o (None, respuesta_error)."""
    datos, fallo = _abrir()
    if fallo:
        return None, fallo
    usuario, ruta, definicion = datos
    definicion = _limpiar_definicion(definicion)
    fila = _sincronizar_bd(usuario, ruta, definicion) or {}
    return (usuario, definicion, fila), None


@bp_encuestas.route('/encuestas/previa', methods=['GET'])
def definicion_previa():
    """Lo mismo que recibe quien responde, más lo que la vista previa usa."""
    datos, fallo = _preparar()
    if fallo:
        return fallo
    usuario, definicion, fila = datos
    carga = publico.carga_publica(fila, definicion, usuario)
    # Las imágenes se sirven por el id del formulario, con la sesión.
    carga['id'] = definicion['id']
    # Una prueba no deja borrador en el navegador: al volver a abrir la vista
    # previa se empieza siempre de cero.
    carga['sin_autoguardado'] = True
    return jsonify({'success': True, 'formulario': carga})


@bp_encuestas.route('/encuestas/previa/validar', methods=['POST'])
def validar_previa():
    """Valida un envío con las reglas de siempre. NO guarda nada.

    Usa `_respuestas_limpias`, la misma función que el envío real: obligatorias
    de las secciones recorridas, tipos, validaciones de cada pregunta. Lo que
    aquí pasa, pasa también al responder de verdad.
    """
    datos, fallo = _preparar()
    if fallo:
        return fallo
    _usuario, definicion, fila = datos

    cuerpo = request.get_json(silent=True) or {}
    enviado = cuerpo.get('respuestas')
    if not isinstance(enviado, dict):
        return error('No se recibió ninguna respuesta.', 400)

    ajustes = ajustes_mod.limpiar(fila.get('ajustes'))
    if ajustes['recopilar_correo'] == ajustes_mod.CORREO_ESCRITO and \
            not correo_mod.correo_valido(cuerpo.get('correo')):
        return error('Escribe un correo electrónico válido.', 400)

    limpias, problema = publico._respuestas_limpias(definicion, enviado)
    if problema:
        return problema
    return jsonify({'success': True, 'previa': True,
                    'respondidas': len(limpias)})
