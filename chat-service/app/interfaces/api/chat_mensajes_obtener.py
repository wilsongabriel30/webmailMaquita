# -*- coding: utf-8 -*-
"""Mensajes: listar (GET) con paginación.
Extraído de chat_mensajes.py (líneas 11-281) el 28/08/2026 sin cambios en las rutas; se registran en bp_chat al importarlo
(lo hace chat_mensajes.py, que sigue siendo el punto de entrada de mensajes)."""
from interfaces.api.chat_base import *  # noqa: F401,F403
from interfaces.api import hora_original


def _horas_escritura(db_session, mensajes_raw):
    """Las horas de escritura (T-49) de toda la pagina, en UNA consulta.

    El objeto que devuelve el dominio no trae los metadatos, y no merece la pena cambiar el
    dominio entero por un dato de presentacion: se piden aparte, de una vez, y solo si hay
    mensajes que pintar.
    """
    ids = [m.get('id') for m in (mensajes_raw or []) if m.get('id')]
    if not ids or db_session is None:
        return {}
    try:
        from sqlalchemy import text
        filas = db_session.execute(text(
            "SELECT id, metadata->>'escrito_en' FROM chat_messages "
            "WHERE id = ANY(:ids) AND metadata ? 'escrito_en'"
        ), {'ids': ids}).fetchall()
        return {f[0]: f[1] for f in filas if f[1]}
    except Exception:
        return {}


def _hora_escritura(m, horas=None):
    """La hora en que se escribio el mensaje (T-49), venga como venga el diccionario."""
    crudo = (m.get('escrito_en')
             or (horas or {}).get(m.get('id'))
             or hora_original.desde_metadata(m.get('metadata'))
             or hora_original.desde_metadata(m.get('msg_metadata')))
    # se muestra con la misma vara que created_at, para que se puedan comparar
    return hora_original.para_mostrar(crudo)


@bp_chat.route('/conversations/<int:conversacion_id>/messages', methods=['GET'])
@bp_chat.route('/conversaciones/<int:conversacion_id>/mensajes', methods=['GET'])  # Alias español
@requiere_autenticacion
def obtener_mensajes(conversacion_id: int):
    """
    Obtiene los mensajes de una conversacion.

    Query params:
        limit: int (default 50)
        before: int (ID del mensaje, para paginacion)

    Response:
        {
            "exito": true,
            "mensajes": [...]
        }
    """
    try:
        limite = request.args.get('limit', 50, type=int)
        antes_de_id = request.args.get('before_id', None, type=int) or request.args.get('before', None, type=int)
        usuario_actual = obtener_usuario_id()

        servicio = obtener_servicio_chat()
        resultado = servicio.obtener_mensajes(
            conversacion_id,
            usuario_actual,
            limite,
            antes_de_id
        )

        if not resultado.exito:
            return jsonify({
                'success': False,
                'exito': False,
                'mensaje': resultado.mensaje
            }), 403

        mensajes_raw = resultado.datos.get('mensajes', [])

        # Respetar "vaciar conversacion": no mostrar a este usuario los mensajes
        # anteriores a su cleared_at (los datos siguen en la BD).
        try:
            from sqlalchemy import text as _t
            ses_cl = g.get('db_session_chat')
            if not ses_cl:
                ses_cl = obtener_gestor().session(); g.db_session_chat = ses_cl
            fila_cl = ses_cl.execute(_t(
                "SELECT cleared_at FROM chat_participants WHERE conversation_id = :c AND user_id = :u"
            ), {'c': conversacion_id, 'u': usuario_actual}).fetchone()
            cleared_at = fila_cl[0] if fila_cl else None
            if cleared_at is not None:
                def _despues(m):
                    f = m.get('creado_en') or m.get('created_at')
                    if not f:
                        return True
                    try:
                        from datetime import datetime as _dt
                        if isinstance(f, str):
                            fdt = _dt.fromisoformat(f.replace('Z', '+00:00'))
                        else:
                            fdt = f
                        ca = cleared_at
                        if fdt.tzinfo and not ca.tzinfo:
                            ca = ca.replace(tzinfo=fdt.tzinfo)
                        elif ca.tzinfo and not fdt.tzinfo:
                            fdt = fdt.replace(tzinfo=ca.tzinfo)
                        return fdt > ca
                    except Exception:
                        return True
                mensajes_raw = [m for m in mensajes_raw if _despues(m)]
        except Exception:
            pass

        # DEBUG: Mostrar cantidad de mensajes cargados y los más recientes
        print(f"[DEBUG-MSG] Conversación {conversacion_id}: {len(mensajes_raw)} mensajes encontrados")
        if mensajes_raw:
            print(f"[DEBUG-MSG] Primer mensaje ID: {mensajes_raw[0].get('id')}, Último mensaje ID: {mensajes_raw[-1].get('id')}")
            # Mostrar los últimos 3 mensajes para diagnóstico
            for msg in mensajes_raw[-3:]:
                print(f"[DEBUG-MSG]   -> ID:{msg.get('id')}, tipo:{msg.get('tipo')}, contenido:'{str(msg.get('contenido', ''))[:30]}...'")

        # Obtener info de remitentes
        # IMPORTANTE: Reutilizar la sesión del servicio para evitar agotar el pool
        from infraestructura.persistencia.modelos.modelo_usuario import ModeloUsuario
        db_session = g.get('db_session_chat')
        if not db_session:
            gestor = obtener_gestor()
            db_session = gestor.session()
            g.db_session_chat = db_session

        try:
            # Recolectar IDs de remitentes
            sender_ids = set(m.get('remitente_id') for m in mensajes_raw if m.get('remitente_id'))

            # Obtener info de usuarios con fallback a foto de trabajador
            usuarios_info = {}
            if sender_ids:
                from sqlalchemy import text
                query_usuarios = text("""
                    SELECT u.id, u.username, u.email, u.full_name, u.role,
                           u.profile_picture, t.foto_perfil as foto_trabajador
                    FROM usuarios u
                    LEFT JOIN trabajadores t ON u.trabajador_id = t.id
                    WHERE u.id = ANY(:user_ids)
                """)
                result = db_session.execute(query_usuarios, {'user_ids': list(sender_ids)})
                usuarios_data = result.fetchall()

                for row in usuarios_data:
                    u_id = row[0]
                    username = row[1]
                    email = row[2]
                    full_name = row[3]
                    role = row[4]
                    profile_picture = row[5]
                    foto_trabajador = row[6]

                    # 2026-06-12: los master tambien aparecen con su nombre real
                    # Usar helper con fallback a foto de trabajador
                    foto_url = obtener_foto_usuario_con_fallback(profile_picture, foto_trabajador)
                    usuarios_info[u_id] = {
                        'id': u_id,
                        'name': full_name or username or email,
                        'photo': foto_url,
                        'is_institutional': False
                    }

            # Lectura de los OTROS participantes (vistos azules del remitente).
            # Un mensaje propio esta leido cuando TODOS los demas participantes
            # activos llegaron a el (last_read_message_id >= id del mensaje).
            min_leido_otros = None
            try:
                query_leido = text("""
                    SELECT MIN(COALESCE(last_read_message_id, 0))
                    FROM chat_participants
                    WHERE conversation_id = :conv_id
                      AND user_id <> :usuario_id
                      AND is_active = TRUE
                """)
                fila_leido = db_session.execute(query_leido, {
                    'conv_id': conversacion_id,
                    'usuario_id': usuario_actual
                }).fetchone()
                if fila_leido and fila_leido[0]:
                    min_leido_otros = fila_leido[0]
            except Exception:
                min_leido_otros = None

            # T-49: las horas de escritura de esta pagina, de una sola vez
            horas_escritura = _horas_escritura(db_session, mensajes_raw)

            # Mapear mensajes para frontend
            mensajes = []
            for m in mensajes_raw:
                sender_id = m.get('remitente_id')
                sender_info = usuarios_info.get(sender_id, {})

                # Mapear archivos para frontend (ruta -> file_path, nombre -> file_name)
                archivos_raw = m.get('archivos', [])
                archivos = []
                for a in archivos_raw:
                    archivos.append({
                        'id': a.get('id'),
                        'type': a.get('tipo'),
                        'file_path': a.get('ruta'),
                        'file_name': a.get('nombre'),
                        'file_size': a.get('tamanio'),
                        'mime_type': a.get('tipo_mime')
                    })

                # Determinar tipo de mensaje y manejar GIFs
                msg_type = m.get('tipo', 'text')
                gif_url = m.get('gif_url')  # URL del GIF desde metadata

                # Debug: verificar tipos de mensaje GIF
                if msg_type == 'gif' or gif_url:
                    print(f"[DEBUG-GIF] msg_id={m.get('id')}, tipo={msg_type}, gif_url={gif_url}")

                # Si es un mensaje de tipo GIF, agregar la URL como media
                if msg_type == 'gif' and gif_url:
                    archivos = [{
                        'id': None,
                        'type': 'gif',
                        'file_path': gif_url,
                        'file_name': 'gif',
                        'media_type': 'gif'
                    }]
                elif archivos and archivos[0].get('type') == 'gif':
                    msg_type = 'gif'
                elif archivos and archivos[0].get('type') == 'image':
                    msg_type = 'image'

                msg = {
                    'id': m.get('id'),
                    'content': m.get('contenido'),
                    'message_type': msg_type,
                    'sender_id': sender_id,
                    'sender': sender_info,
                    'sender_name': sender_info.get('name', 'Usuario'),
                    'sender_photo': sender_info.get('photo'),
                    'created_at': m.get('creado_en'),
                    # T-49: si el mensaje espero en la cola del equipo, aqui viaja la hora
                    # en que se escribio para poder mostrar "escrito 10:02 - entregado 10:20"
                    'escrito_en': _hora_escritura(m, horas_escritura),
                    'is_own_message': sender_id == usuario_actual,
                    'is_read': bool(min_leido_otros and m.get('id')
                                     and sender_id == usuario_actual
                                     and m.get('id') <= min_leido_otros),
                    'is_edited': m.get('editado', False),
                    'is_deleted': m.get('eliminado', False),
                    'reply_to_id': m.get('respuesta_a_id'),
                    'forwarded_from_id': m.get('forwarded_from_id'),
                    'media': archivos,
                    'reactions': m.get('reacciones', {}),
                    'gif_url': gif_url  # Agregar gif_url directamente para fallback
                }
                mensajes.append(msg)

        finally:
            # No cerrar aquí - se cierra en teardown_request
            pass

        # Citas de los mensajes que responden a otro (Responder)
        try:
            from interfaces.api.citas_respuesta import enriquecer_citas
            enriquecer_citas(mensajes, servicio)
        except Exception:
            pass

        # Drive ↔ chat (T-18): ocultar, para este usuario, los adjuntos que quitó de su Drive
        try:
            from interfaces.api.drive_eventos_api import aplicar_ocultos
            aplicar_ocultos(mensajes, usuario_actual)
        except Exception:
            pass

        # Vistos: lo listado queda ENTREGADO al lector; los propios se anotan con delivered_at
        try:
            from interfaces.api.estado_entrega import registrar_entrega_al_listar, anotar_entregados
            _nuevos = registrar_entrega_al_listar(db_session, conversacion_id, usuario_actual,
                                                  [m['id'] for m in mensajes if m.get('id')])
            anotar_entregados(mensajes, db_session, conversacion_id, usuario_actual)
            if _nuevos:
                emitir_a_conversacion(conversacion_id, 'msg_status',
                                      {'ids': _nuevos, 'c': conversacion_id, 'status': 'delivered', 'by': usuario_actual})
        except Exception:
            pass

        return jsonify({
            'success': True,
            'exito': True,
            'messages': mensajes,
            'mensajes': mensajes,
            'has_more': len(mensajes) >= limite
        }), 200

    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"[ERROR] obtener_mensajes - EXCEPCION: {error_msg}")
        traceback.print_exc()

        # Intentar hacer rollback para limpiar la sesión
        db_session = g.get('db_session_chat')
        if db_session:
            try:
                db_session.rollback()
            except:
                pass

        return jsonify({
            'success': False,
            'exito': False,
            'mensaje': f'Error al cargar mensajes: {error_msg}'
        }), 500
