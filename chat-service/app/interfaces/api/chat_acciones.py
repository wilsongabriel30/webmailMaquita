# -*- coding: utf-8 -*-
"""Acciones en conversación (escribiendo, grabando…).
Extraído de controlador_chat.py (líneas 2439-2621) el 28/08/2026 sin cambios en las rutas. Las rutas se registran en
bp_chat al importar este módulo (lo hace controlador_chat.py, que sigue siendo el punto de entrada)."""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, servicio, autenticación…)

# =============================================================================
# INDICADORES DE ACCION (ESCRIBIENDO, GRABANDO, ETC.)
# =============================================================================

@bp_chat.route('/conversations/<int:conversacion_id>/action', methods=['POST'])
@requiere_autenticacion
def establecer_accion(conversacion_id: int):
    """
    Establece la accion actual del usuario en una conversacion.

    Request:
        {
            "accion": "typing" | "recording_audio" | "recording_video" |
                      "uploading" | "taking_photo" | "choosing_sticker" | "none"
        }

    Response:
        {
            "exito": true,
            "mensaje": "OK"
        }
    """
    try:
        datos = request.get_json() or {}
        accion = datos.get('accion', 'typing')

        servicio = obtener_servicio_chat()
        resultado = servicio.establecer_accion(
            conversacion_id=conversacion_id,
            usuario_id=obtener_usuario_id(),
            accion=accion
        )

        status = 200 if resultado.exito else 400
        return jsonify({
            'exito': resultado.exito,
            'mensaje': resultado.mensaje
        }), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/conversations/<int:conversacion_id>/action', methods=['DELETE'])
@requiere_autenticacion
def limpiar_accion(conversacion_id: int):
    """
    Limpia la accion del usuario (deja de escribir/grabar).

    Response:
        {
            "exito": true,
            "mensaje": "OK"
        }
    """
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.limpiar_accion(
            conversacion_id=conversacion_id,
            usuario_id=obtener_usuario_id()
        )

        return jsonify({
            'exito': resultado.exito,
            'mensaje': resultado.mensaje
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/conversations/<int:conversacion_id>/actions', methods=['GET'])
@requiere_autenticacion
def obtener_acciones(conversacion_id: int):
    """
    Obtiene las acciones activas en una conversacion.

    Retorna quienes estan escribiendo, grabando, etc.

    Response:
        {
            "exito": true,
            "acciones": [
                {"usuario_id": 1, "accion": "typing", "inicio": "2026-01-02T10:00:00"},
                {"usuario_id": 2, "accion": "recording_audio", "inicio": "2026-01-02T10:00:05"}
            ]
        }
    """
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.obtener_acciones_conversacion(
            conversacion_id=conversacion_id,
            usuario_id=obtener_usuario_id()
        )

        if not resultado.exito:
            return jsonify({
                'exito': False,
                'mensaje': resultado.mensaje
            }), 403

        return jsonify({
            'exito': True,
            'acciones': resultado.datos.get('acciones', [])
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/conversations/<int:conversacion_id>/typing', methods=['POST'])
@requiere_autenticacion
def iniciar_escribiendo(conversacion_id: int):
    """
    Atajo para indicar que el usuario esta escribiendo.
    Equivalente a POST /action con {"accion": "typing"}

    Response:
        {
            "exito": true
        }
    """
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.establecer_accion(
            conversacion_id=conversacion_id,
            usuario_id=obtener_usuario_id(),
            accion='typing'
        )

        return jsonify({'exito': resultado.exito}), 200

    except Exception as e:
        # El indicador de typing no es critico - si falla, simplemente ignorar
        # No queremos que errores de typing bloqueen la experiencia del usuario
        import logging
        logging.getLogger(__name__).warning(f"Error en typing (no critico): {e}")
        return jsonify({'exito': True}), 200  # Devolver exito aunque falle internamente


@bp_chat.route('/conversations/<int:conversacion_id>/typing', methods=['DELETE'])
@requiere_autenticacion
def detener_escribiendo(conversacion_id: int):
    """
    Atajo para indicar que el usuario dejo de escribir.
    Equivalente a DELETE /action

    Response:
        {
            "exito": true
        }
    """
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.limpiar_accion(
            conversacion_id=conversacion_id,
            usuario_id=obtener_usuario_id()
        )

        return jsonify({'exito': resultado.exito}), 200

    except Exception as e:
        # El indicador de typing no es critico - si falla, simplemente ignorar
        import logging
        logging.getLogger(__name__).warning(f"Error en stop_typing (no critico): {e}")
        return jsonify({'exito': True}), 200  # Devolver exito aunque falle internamente

