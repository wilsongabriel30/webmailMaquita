# -*- coding: utf-8 -*-
"""Presencia en línea y bloqueos.
Extraído de controlador_chat.py (líneas 1991-2183) el 28/08/2026 sin cambios en las rutas. Las rutas se registran en
bp_chat al importar este módulo (lo hace controlador_chat.py, que sigue siendo el punto de entrada)."""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, servicio, autenticación…)

# =============================================================================
# PRESENCIA
# =============================================================================

@bp_chat.route('/presence', methods=['POST'])
@bp_chat.route('/presence/update', methods=['POST'])  # Alias para compatibilidad
@bp_chat.route('/presence/offline', methods=['POST'])  # Alias para marcar offline
@requiere_autenticacion
def actualizar_presencia():
    """
    Actualiza la presencia del usuario.

    Request:
        {
            "online": true/false
        }

    Response:
        {
            "exito": true
        }
    """
    try:
        # Usar silent=True para evitar error si no hay JSON o Content-Type incorrecto
        datos = request.get_json(silent=True) or {}

        # Si la ruta es /offline, marcar como offline
        if request.path.endswith('/offline'):
            en_linea = False
        else:
            en_linea = datos.get('online', True)

        servicio = obtener_servicio_chat()
        usuario_id = obtener_usuario_id()
        servicio.actualizar_presencia(usuario_id, en_linea)

        # T-48: si dice que se va, se le cree y se borra su senal de vida; si sigue aqui,
        # se anota la actividad. Sin esto el puntito seguia diciendo "conectado" hasta que
        # caducaba la clave del socket (hasta 5 minutos despues de cerrar la aplicacion).
        try:
            from interfaces.websocket import estado_presencia
            from interfaces.websocket import manejador_websocket as _mw
            if en_linea:
                estado_presencia.marcar_actividad(usuario_id)
            elif _mw._ws_redis:
                _mw._ws_redis.delete(estado_presencia.CLAVE_CONEXION % usuario_id)
                _mw._ws_redis.delete(estado_presencia.CLAVE_ACTIVIDAD % usuario_id)
                estado_presencia.marcar_en_llamada(usuario_id, False)
        except Exception:
            pass

        return jsonify({'exito': True, 'success': True}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] actualizar_presencia - {str(e)}")
        # Retornar 200 para no bloquear el frontend (la presencia no es critica)
        return jsonify({
            'exito': True,
            'success': True,
            'mensaje': 'Presencia no actualizada'
        }), 200


@bp_chat.route('/presence/<int:usuario_id>', methods=['GET'])
@requiere_autenticacion
def obtener_presencia_usuario(usuario_id: int):
    """
    Obtiene la presencia de un usuario.

    Response:
        {
            "exito": true,
            "online": true/false,
            "last_seen": "ISO datetime"
        }
    """
    try:
        servicio = obtener_servicio_chat()
        presencias = servicio.obtener_presencia([usuario_id])
        presencia = presencias.get(usuario_id, {'online': False, 'last_seen': None})

        return jsonify({
            'exito': True,
            'online': presencia['online'],
            'last_seen': presencia['last_seen'].isoformat() if presencia['last_seen'] else None
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


# =============================================================================
# BLOQUEOS
# =============================================================================

@bp_chat.route('/block/<int:usuario_id>', methods=['POST'])
@requiere_autenticacion
def bloquear_usuario(usuario_id: int):
    """
    Bloquea a un usuario.

    Request (opcional):
        {
            "razon": "texto"
        }

    Response:
        {
            "exito": true,
            "mensaje": "Usuario bloqueado"
        }
    """
    try:
        datos = request.get_json() or {}
        razon = datos.get('razon')

        servicio = obtener_servicio_chat()
        resultado = servicio.bloquear_usuario(
            bloqueador_id=obtener_usuario_id(),
            bloqueado_id=usuario_id,
            razon=razon
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


@bp_chat.route('/block/<int:usuario_id>', methods=['DELETE'])
@requiere_autenticacion
def desbloquear_usuario(usuario_id: int):
    """
    Desbloquea a un usuario.

    Response:
        {
            "exito": true,
            "mensaje": "Usuario desbloqueado"
        }
    """
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.desbloquear_usuario(
            bloqueador_id=obtener_usuario_id(),
            bloqueado_id=usuario_id
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


@bp_chat.route('/blocked', methods=['GET'])
@requiere_autenticacion
def obtener_bloqueados():
    """
    Obtiene la lista de usuarios bloqueados.

    Response:
        {
            "exito": true,
            "bloqueados": [1, 2, 3]
        }
    """
    try:
        servicio = obtener_servicio_chat()
        bloqueados = servicio.obtener_bloqueados(obtener_usuario_id())

        return jsonify({
            'exito': True,
            'bloqueados': bloqueados
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500

