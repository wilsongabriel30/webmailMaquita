# -*- coding: utf-8 -*-
"""Latido y presencia. Extraído de manejador_websocket._registrar_eventos (líneas 819-889) el 28/08/2026 sin cambios.
Los manejadores se registran al llamar registrar(socketio) desde manejador_websocket._registrar_eventos()."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _actualizar_presencia_bd, _cerrar_servicio, _obtener_servicio_chat, _ws_redis  # noqa: F401


def registrar(socketio):
    # =========================================================================
    # PRESENCIA
    # =========================================================================

    @socketio.on('heartbeat')
    def heartbeat():
        """
        Heartbeat para mantener la conexion y actualizar presencia.

        El cliente debe enviar esto cada 30 segundos.
        """
        usuario_id = session.get('usuario_id')
        if usuario_id:
            _actualizar_presencia_bd(usuario_id, True)
            # Refresh Redis presence + connection TTLs
            if _ws_redis:
                try:
                    _ws_redis.set(f"chat:presence:{usuario_id}", "online", ttl_segundos=300)
                    _ws_redis.expire(f"chat:ws:user:{usuario_id}", 3600)
                except Exception:
                    pass
            emit('heartbeat_ack', {'timestamp': datetime.now().isoformat()})

    @socketio.on('get_presence')
    def obtener_presencia(data):
        """
        Obtiene la presencia de uno o varios usuarios.

        Args:
            data: {'user_ids': [int, int, ...]}

        Emite:
            'presence_info' con el estado de cada usuario
        """
        usuario_ids = data.get('user_ids', [])
        usuario_id = session.get('usuario_id')
        if not usuario_ids or not usuario_id:
            return

        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            # [M-03] solo la presencia de quienes comparten conversación con quien pregunta
            from interfaces import relacion_chat
            usuario_ids = relacion_chat.filtrar_visibles(
                servicio._db_session, usuario_id, usuario_ids, _ws_redis)
            if not usuario_ids:
                emit('presence_info', {})
                return
            presencias = servicio.obtener_presencia(usuario_ids)

            resultado = {}
            for uid in usuario_ids:
                # Check local + Redis
                en_linea = (uid in usuarios_conectados and usuarios_conectados[uid])
                if not en_linea and _ws_redis:
                    try:
                        en_linea = _ws_redis.exists(f"chat:presence:{uid}")
                    except Exception:
                        pass
                if en_linea:
                    resultado[uid] = {'online': True, 'last_seen': None}
                elif uid in presencias:
                    p = presencias[uid]
                    resultado[uid] = {
                        'online': p.get('online', False),
                        'last_seen': p.get('last_seen').isoformat() if p.get('last_seen') else None
                    }
                else:
                    resultado[uid] = {'online': False, 'last_seen': None}

            emit('presence_info', resultado)
        except Exception as e:
            logger.error(f"[WebSocket] Error en get_presence: {e}")
            emit('presence_info', {})
        finally:
            if servicio:
                _cerrar_servicio(servicio)

