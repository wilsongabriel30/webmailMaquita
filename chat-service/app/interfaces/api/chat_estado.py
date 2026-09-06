# -*- coding: utf-8 -*-
"""T-48 - Endpoints del estado de presencia (los que llama el cliente Windows).

  POST /api/chat/estado           {"estado": "conectado|ausente|ocupado"}  guarda la eleccion
  GET  /api/chat/estado                                                    el propio, para el puntito
  GET  /api/chat/estado/<id>                                               el de otra persona
  POST /api/chat/estado/varios    {"usuarios": [1,2,3]}                    varios de una vez

La REGLA de que puntito se ve no esta aqui, sino en interfaces/websocket/estado_presencia.py:
asi la usan igual estos endpoints, la lista de conversaciones y la ficha del companero.
"""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, autenticacion)
from interfaces.websocket import estado_presencia as regla


def _visibles(ids):
    """[M-03] De `ids`, los que comparten conversación con quien pregunta (fallo cerrado)."""
    from interfaces import relacion_chat
    from interfaces.websocket import manejador_websocket as mw
    try:
        servicio = obtener_servicio_chat()
        return relacion_chat.filtrar_visibles(servicio._db_session, obtener_usuario_id(), ids, mw._ws_redis)
    except Exception:
        return []


def _avisar_a_los_demas(usuario_id, estado):
    """Avisa por el socket para que el puntito cambie en las pantallas de los demas,
    sin que nadie tenga que recargar."""
    try:
        from interfaces.websocket import manejador_websocket as mw
        if mw.socketio:
            # [L-01] solo a quienes comparten conversación, no a todos los conectados
            for destino in mw._relacionados_de(usuario_id):
                mw.socketio.emit('estado_presencia', {'usuario_id': usuario_id, 'estado': estado},
                                 room=f"user_{destino}")
    except Exception:
        pass   # el aviso es un extra: si falla, el estado ya quedo guardado


@bp_chat.route('/estado', methods=['POST'])
@requiere_autenticacion
def guardar_estado():
    datos = request.get_json(silent=True) or {}
    estado = regla.normalizar(datos.get('estado'))
    if estado is None:
        return jsonify({'exito': False, 'success': False,
                        'mensaje': 'estado debe ser uno de: %s (o "auto" para restablecer)'
                                   % ', '.join(regla.VALIDOS)}), 400
    usuario_id = obtener_usuario_id()
    regla.guardar_eleccion(usuario_id, estado)
    efectivo = regla.estado_de(usuario_id)
    _avisar_a_los_demas(usuario_id, efectivo)
    return jsonify({'exito': True, 'success': True,
                    'elegido': estado, 'estado': efectivo}), 200


@bp_chat.route('/estado', methods=['GET'])
@requiere_autenticacion
def mi_estado():
    usuario_id = obtener_usuario_id()
    regla.marcar_actividad(usuario_id)
    detalle = regla.detalle_de(usuario_id)
    detalle.update({'exito': True, 'success': True, 'usuario_id': usuario_id})
    return jsonify(detalle), 200


@bp_chat.route('/estado/<int:usuario_id>', methods=['GET'])
@requiere_autenticacion
def estado_de_otro(usuario_id: int):
    # [M-03] solo de quien comparte conversación conmigo
    if not _visibles([usuario_id]):
        return jsonify({'exito': False, 'success': False, 'mensaje': 'Usuario no encontrado'}), 404
    return jsonify({'exito': True, 'success': True,
                    'usuario_id': usuario_id, 'estado': regla.estado_de(usuario_id)}), 200


@bp_chat.route('/estado/varios', methods=['POST'])
@requiere_autenticacion
def estado_de_varios():
    datos = request.get_json(silent=True) or {}
    usuarios = [int(u) for u in (datos.get('usuarios') or []) if str(u).isdigit()]
    usuarios = _visibles(usuarios)   # [M-03] los demás simplemente no salen
    return jsonify({'exito': True, 'success': True,
                    'estados': regla.estados_de(usuarios)}), 200
