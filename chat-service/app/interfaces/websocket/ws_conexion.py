# -*- coding: utf-8 -*-
"""Conexión y desconexión. Extraído de manejador_websocket._registrar_eventos (líneas 248-354) el 28/08/2026 sin cambios.
Los manejadores se registran al llamar registrar(socketio) desde manejador_websocket._registrar_eventos()."""
import os

from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _actualizar_presencia_bd, _emitir_presencia, _ws_redis, sesion_de_socket  # noqa: F401


def registrar(socketio):
    # =========================================================================
    # CONEXION Y DESCONEXION
    # =========================================================================

    @socketio.on('connect')
    def manejar_conexion():
        """
        Maneja una nueva conexion WebSocket.

        El cliente debe estar autenticado via sesion Flask.
        Automaticamente une al usuario a sus rooms de conversaciones.
        """
        usuario_id = session.get('usuario_id')

        if not usuario_id:
            logger.warning(f"[WebSocket] Conexion rechazada: no autenticado (sid={request.sid})")
            disconnect()
            return False

        # F-03: misma regla que las peticiones REST: la sesión central tiene que valer.
        if os.getenv('CHAT_SESION_CENTRAL', '1') != '0':
            from interfaces.api.sesion_central import sesion_central_valida
            if not sesion_central_valida():
                logger.warning(f"[WebSocket] Conexion rechazada: sesion central no valida (usuario={usuario_id})")
                disconnect()
                return False

        sid = request.sid
        sesion_de_socket[sid] = session.get('sid')

        # Registrar conexion (local)
        if usuario_id not in usuarios_conectados:
            usuarios_conectados[usuario_id] = set()
        usuarios_conectados[usuario_id].add(sid)
        sid_a_usuario[sid] = usuario_id

        # Registrar en Redis (distribuido)
        if _ws_redis:
            try:
                _ws_redis.sadd(f"chat:ws:user:{usuario_id}", sid)
                _ws_redis.expire(f"chat:ws:user:{usuario_id}", 3600)
                _ws_redis.hset("chat:ws:sid_map", sid, str(usuario_id))
                _ws_redis.set(f"chat:presence:{usuario_id}", "online", ttl_segundos=300)
            except Exception as e:
                logger.warning(f"[WebSocket] Redis registro conexion error: {e}")

        # Unir a room personal (para mensajes directos al usuario)
        join_room(f"user_{usuario_id}")

        # Actualizar presencia en BD
        _actualizar_presencia_bd(usuario_id, True)

        # Notificar a contactos que el usuario esta online
        _emitir_presencia(usuario_id, True)

        logger.info(f"[WebSocket] Usuario {usuario_id} conectado (sid={sid})")

        # Confirmar conexion al cliente
        emit('connected', {
            'usuario_id': usuario_id,
            'timestamp': datetime.now().isoformat()
        })

        return True

    @socketio.on('disconnect')
    def manejar_desconexion():
        """
        Maneja la desconexion de un cliente WebSocket.

        Limpia el registro y notifica a contactos.
        """
        sid = request.sid
        usuario_id = sid_a_usuario.get(sid)

        if usuario_id:
            # Remover esta conexion (local)
            if usuario_id in usuarios_conectados:
                usuarios_conectados[usuario_id].discard(sid)
                sesion_de_socket.pop(sid, None)

                # Si no tiene mas conexiones en este worker, marcar como offline
                if not usuarios_conectados[usuario_id]:
                    del usuarios_conectados[usuario_id]

                    # Verificar en Redis si hay otras conexiones en otros workers
                    tiene_otras = False
                    if _ws_redis:
                        try:
                            _ws_redis.srem(f"chat:ws:user:{usuario_id}", sid)
                            _ws_redis.hdel("chat:ws:sid_map", sid)
                            remaining = _ws_redis.scard(f"chat:ws:user:{usuario_id}")
                            tiene_otras = remaining > 0
                        except Exception:
                            pass

                    if not tiene_otras:
                        _actualizar_presencia_bd(usuario_id, False)
                        # T-48: si se fue, ya no esta en ninguna llamada
                        try:
                            from interfaces.websocket import estado_presencia
                            estado_presencia.marcar_en_llamada(usuario_id, False)
                        except Exception:
                            pass
                        _emitir_presencia(usuario_id, False)
                        if _ws_redis:
                            try:
                                _ws_redis.delete(f"chat:presence:{usuario_id}")
                            except Exception:
                                pass
            elif _ws_redis:
                # Limpiar Redis aunque no estaba en local
                try:
                    _ws_redis.srem(f"chat:ws:user:{usuario_id}", sid)
                    _ws_redis.hdel("chat:ws:sid_map", sid)
                except Exception:
                    pass

            if sid in sid_a_usuario:
                del sid_a_usuario[sid]

            logger.info(f"[WebSocket] Usuario {usuario_id} desconectado (sid={sid})")

