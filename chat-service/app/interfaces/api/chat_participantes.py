# -*- coding: utf-8 -*-
"""Participantes de grupos: agregar, quitar, salir.
Extraído de controlador_chat.py (líneas 1859-1990) el 28/08/2026 sin cambios en las rutas. Las rutas se registran en
bp_chat al importar este módulo (lo hace controlador_chat.py, que sigue siendo el punto de entrada)."""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, servicio, autenticación…)

# =============================================================================
# PARTICIPANTES
# =============================================================================

@bp_chat.route('/conversations/<int:conversacion_id>/participants', methods=['POST'])
@requiere_autenticacion
def agregar_participante(conversacion_id: int):
    """
    Agrega un participante a un grupo.

    Request:
        {
            "usuario_id": int
        }

    Response:
        {
            "exito": true,
            "mensaje": "Participante agregado"
        }
    """
    try:
        datos = request.get_json()
        if not datos or 'usuario_id' not in datos:
            return jsonify({
                'exito': False,
                'mensaje': 'usuario_id es requerido'
            }), 400

        # Aislamiento por dominio (multi-empresa)
        try:
            import tenant_chat as _tc
            if _tc.aislamiento_activo():
                _db = g.get('db_session_chat')
                if not _db:
                    from infraestructura.base_datos.base import obtener_gestor as _og
                    _db = _og().session(); g.db_session_chat = _db
                if _tc.primer_bloqueado(_db, obtener_usuario_id(), [int(datos['usuario_id'])]) is not None:
                    return jsonify({'exito': False, 'mensaje': 'No puedes agregar usuarios de otra organizacion'}), 403
        except Exception:
            pass
        servicio = obtener_servicio_chat()
        resultado = servicio.agregar_participante(
            conversacion_id=conversacion_id,
            admin_id=obtener_usuario_id(),
            usuario_id=datos['usuario_id']
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


@bp_chat.route('/conversations/<int:conversacion_id>/participants/<int:usuario_id>', methods=['DELETE'])
@requiere_autenticacion
def eliminar_participante(conversacion_id: int, usuario_id: int):
    """
    Elimina un participante de un grupo.

    Response:
        {
            "exito": true,
            "mensaje": "Participante eliminado"
        }
    """
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.eliminar_participante(
            conversacion_id=conversacion_id,
            admin_id=obtener_usuario_id(),
            usuario_id=usuario_id
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


@bp_chat.route('/conversations/<int:conversacion_id>/leave', methods=['POST'])
@requiere_autenticacion
def salir_de_grupo(conversacion_id: int):
    """
    El usuario sale del grupo.

    Response:
        {
            "exito": true,
            "mensaje": "Has salido del grupo"
        }
    """
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.salir_de_grupo(
            conversacion_id=conversacion_id,
            usuario_id=obtener_usuario_id()
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

