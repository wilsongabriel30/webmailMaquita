# -*- coding: utf-8 -*-
"""Canal rápido: evento `send` (ACK instantáneo, idempotencia, emisión compacta). Extraído de ws_canal_rapido.py el 28/08/2026
sin cambios; los alias (join/leave/typing/read/ping_chat) están en ws_canal_rapido_alias.py y typing_with_expire en ws_escribiendo_expira.py."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _cerrar_servicio, _commit_servicio, _es_participante, _limpiar_indicador, _obtener_mensaje_por_client_id, _obtener_servicio_chat, _registrar_client_id, _typing_timers  # noqa: F401


def registrar(socketio, base):
    @socketio.on('send')
    def enviar_mensaje_rapido(data):
        """
        Envio de mensaje ultra-rapido con ACK instantaneo e idempotencia.

        Formato compacto para minima latencia:
        - c: conversation_id
        - m: message content
        - t: temp_id/client_id (ID temporal del cliente para idempotencia)
        - type: tipo de mensaje

        Flujo:
        1. Valida autenticacion, permisos y rate limit
        2. Verifica idempotencia (si client_id ya fue procesado)
        3. Emite 'ack' inmediatamente (antes de guardar en BD)
        4. Guarda en BD con client_id
        5. Emite 'msg_saved' con ID real o 'msg_failed' si falla
        6. Emite 'msg' a otros participantes
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            emit('error', {'message': 'No autenticado'})
            return

        conversacion_id = data.get('c') or data.get('conversation_id')
        contenido = (data.get('m') or data.get('content', '')).strip()
        client_id = data.get('t') or data.get('temp_id') or data.get('client_id')
        tipo = data.get('type', 'text')
        respuesta_a = data.get('reply_to') or data.get('r')
        try:
            respuesta_a = int(respuesta_a) if respuesta_a else None
        except (TypeError, ValueError):
            respuesta_a = None

        # Un GIF/media puede ir sin texto: basta con gif_url/url
        _tiene_media = bool(data.get('gif_url') or data.get('url'))

        # Validaciones basicas (texto requerido SOLO si no hay media)
        if not conversacion_id or (not contenido and not _tiene_media):
            emit('msg_failed', {
                't': client_id,
                'reason': 'c y m requeridos',
                'code': 'INVALID_DATA'
            })
            return

        # Rate limiting
        if not check_rate_limit('send', usuario_id):
            emit('msg_failed', {
                't': client_id,
                'reason': 'Demasiados mensajes. Espera un momento.',
                'code': 'RATE_LIMITED'
            })
            return

        # Verificar permisos (es participante de la conversacion)
        if not _es_participante(usuario_id, conversacion_id):
            emit('msg_failed', {
                't': client_id,
                'reason': 'No tienes acceso a esta conversacion',
                'code': 'FORBIDDEN'
            })
            return

        # ========== IDEMPOTENCIA ==========
        # Verificar si este client_id ya fue procesado
        mensaje_existente = _obtener_mensaje_por_client_id(client_id)
        if mensaje_existente:
            # Ya fue procesado - retornar el mensaje existente sin duplicar
            logger.info(f"[WebSocket] Mensaje duplicado detectado: {client_id} -> {mensaje_existente}")
            emit('ack', {
                't': client_id,
                'ts': datetime.now().timestamp() * 1000
            })
            emit('msg_saved', {
                't': client_id,
                'id': mensaje_existente,
                's': 'saved',
                'duplicate': True
            })
            return

        # 1. ACK INSTANTANEO (antes de cualquier operacion de BD)
        emit('ack', {
            't': client_id,
            'ts': datetime.now().timestamp() * 1000
        })

        servicio = None
        gif_url = data.get('gif_url') or data.get('url')  # URL del GIF si es tipo gif

        try:
            # 2. Guardar en BD con client_id para idempotencia
            print(f"[WS-DEBUG] Enviando mensaje: conv={conversacion_id}, user={usuario_id}, client_id={client_id}, tipo={tipo}")
            servicio = _obtener_servicio_chat()

            # Si es un GIF, usar el servicio de GIF
            if tipo == 'gif' and gif_url:
                resultado = servicio.enviar_gif(
                    conversacion_id=conversacion_id,
                    remitente_id=usuario_id,
                    url_gif=gif_url,
                    contenido=contenido or 'GIF'
                )
            else:
                resultado = servicio.enviar_mensaje(
                    conversacion_id=conversacion_id,
                    remitente_id=usuario_id,
                    contenido=contenido,
                    tipo=tipo,
                    respuesta_a_id=respuesta_a,
                    client_id=client_id  # Para constraint UNIQUE en BD
                )
            print(f"[WS-DEBUG] Resultado enviar_mensaje: exito={resultado.exito}, mensaje={resultado.mensaje}")

            if resultado.exito:
                # IMPORTANTE: Commit para persistir el mensaje
                print(f"[WS-DEBUG] Haciendo commit...")
                _commit_servicio(servicio)
                print(f"[WS-DEBUG] Commit exitoso")

                mensaje_data = resultado.datos.get('mensaje', {})
                mensaje_id = mensaje_data.get('id')

                # Registrar client_id como procesado (cache local)
                _registrar_client_id(client_id, mensaje_id)

                # 3. Confirmar guardado al remitente
                emit('msg_saved', {
                    't': client_id,
                    'id': mensaje_id,
                    's': 'saved'
                })

                # 4. Emitir a otros en la conversacion (formato compacto)
                room = f"conversation_{conversacion_id}"
                print(f"[WebSocket] ⚡⚡⚡ Emitiendo 'msg' a sala {room} (mensaje {mensaje_id} de usuario {usuario_id})")
                print(f"[WebSocket] Usuarios conectados: {list(usuarios_conectados.keys())}")
                print(f"[WebSocket] SID actual (skip): {request.sid}")

                # Debug: Listar SIDs y ver clientes en la sala destino
                try:
                    # Mostrar qué SIDs están en qué usuarios
                    for uid, sids in usuarios_conectados.items():
                        for sid in sids:
                            print(f"[WebSocket] 🔍 Usuario {uid} tiene SID {sid}")

                    # Intentar ver cuántos clientes hay en la sala
                    if socketio.server and hasattr(socketio.server, 'manager'):
                        try:
                            rooms_info = socketio.server.manager.get_participants('/', room)
                            sids_en_sala = list(rooms_info) if rooms_info else []
                            print(f"[WebSocket] 📊 Clientes en sala {room}: {sids_en_sala}")
                            print(f"[WebSocket] 📊 Total clientes en sala: {len(sids_en_sala)}")
                        except Exception as inner_e:
                            print(f"[WebSocket] No se pudo obtener participantes: {inner_e}")
                except Exception as e:
                    print(f"[WebSocket] Error listando rooms: {e}")

                # Preparar datos del mensaje
                msg_data = {
                    'id': mensaje_id,
                    't': client_id,
                    'c': conversacion_id,
                    'm': contenido,
                    'from': usuario_id,
                    'nombre': session.get('usuario_nombre', 'Usuario'),
                    'ts': datetime.now().timestamp() * 1000,
                    'type': tipo,
                    'r': respuesta_a
                }

                # Si es un GIF, incluir la URL
                if tipo == 'gif' and gif_url:
                    msg_data['gif_url'] = gif_url
                    msg_data['media'] = [{
                        'file_path': gif_url,
                        'media_type': 'gif'
                    }]

                print(f"[WebSocket] 📤 Emitiendo msg_data: {msg_data}")
                socketio.emit('msg', msg_data, room=room, skip_sid=request.sid)
                print(f"[WebSocket] ✅ emit() ejecutado a sala {room}")

                # Canal único de notificaciones (evento 'notificacion' a user_<id>)
                try:
                    from interfaces.websocket.notificaciones_globales import notificar_mensaje
                    notificar_mensaje(conversacion_id, usuario_id, session.get('usuario_nombre', 'Usuario'),
                                      contenido, tipo, mensaje_id, data.get('mentions'))
                except Exception as _e:
                    print(f"[notificaciones] {_e}")

                # ⚡ SINCRONIZAR OTRAS VENTANAS DEL MISMO USUARIO
                # Emitir a todos los SIDs del remitente (excepto el actual) para sincronizar
                # sus otras ventanas/pestañas (ej: chat grande y mini-chat)
                current_sid = request.sid
                user_sids = usuarios_conectados.get(usuario_id, [])
                for other_sid in user_sids:
                    if other_sid != current_sid:
                        # Agregar flag para que el cliente sepa que es un mensaje propio
                        sync_data = {**msg_data, 'is_own_sync': True}
                        socketio.emit('msg', sync_data, to=other_sid)
                        print(f"[WebSocket] 🔄 Sincronizado a otra ventana del usuario: {other_sid}")

                # Limpiar indicador de escritura
                _limpiar_indicador(conversacion_id, usuario_id)

                print(f"[WebSocket] Mensaje {mensaje_id} emitido exitosamente a {room}")
                logger.info(f"[WebSocket] Mensaje {mensaje_id} enviado por {usuario_id} a {room}")
            else:
                # Error al guardar - emitir msg_failed
                logger.warning(f"[WebSocket] Error guardando mensaje: {resultado.mensaje}")
                emit('msg_failed', {
                    't': client_id,
                    'reason': resultado.mensaje,
                    'code': 'DB_ERROR',
                    'retry': True  # El cliente puede reintentar
                })

        except Exception as e:
            import traceback
            print(f"[WS-DEBUG] ERROR en send: {e}")
            traceback.print_exc()
            logger.error(f"[WebSocket] Error en send: {e}")
            emit('msg_failed', {
                't': client_id,
                'reason': 'Error interno del servidor',
                'code': 'INTERNAL_ERROR',
                'retry': True
            })
        finally:
            # Siempre cerrar la sesion
            if servicio:
                _cerrar_servicio(servicio)
