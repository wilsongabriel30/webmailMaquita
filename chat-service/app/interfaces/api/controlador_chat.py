# -*- coding: utf-8 -*-
"""
Controlador API: Chat Institucional

Maneja las rutas HTTP REST del chat.
Es un adaptador de entrada que traduce HTTP a operaciones del ServicioChat.

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

from flask import Blueprint, request, jsonify, session, g
from functools import wraps
from typing import Optional
from datetime import datetime

from aplicacion.servicios.servicio_chat import ServicioChat
from interfaces.websocket import emitir_mensaje_nuevo, emitir_a_conversacion, emitir_notificacion
from infraestructura.base_datos.base import obtener_gestor
from infraestructura.persistencia.repositorio_chat_postgresql import (
    RepositorioConversacionPostgreSQL,
    RepositorioParticipantePostgreSQL,
    RepositorioMensajePostgreSQL,
    RepositorioArchivoMensajePostgreSQL,
    RepositorioReaccionPostgreSQL,
    RepositorioPresenciaPostgreSQL,
    RepositorioBloqueoPostgreSQL,
    RepositorioIndicadorAccionPostgreSQL
)


# Blueprint para rutas del chat
bp_chat = Blueprint('chat', __name__, url_prefix='/api/chat')


def obtener_foto_usuario_con_fallback(profile_picture: str, foto_trabajador: str) -> str:
    """
    Obtiene la URL de foto del usuario con fallback a foto de trabajador.

    Prioridad:
    1. profile_picture del usuario (si existe y no está vacío)
    2. foto_perfil del trabajador vinculado (fallback)
    3. None si no hay ninguna

    Args:
        profile_picture: Foto de perfil del usuario (puede ser None)
        foto_trabajador: Foto del trabajador vinculado (puede ser None)

    Returns:
        URL completa de la foto o None
    """
    # Primero intentar con profile_picture del usuario
    foto = profile_picture
    prefijo = '/static/uploads/profiles/'

    # Si no hay profile_picture, usar foto del trabajador
    if not foto and foto_trabajador:
        foto = foto_trabajador
        prefijo = '/static/'

    if not foto:
        return None

    # Construir URL completa
    if foto.startswith(('http://', 'https://')):
        return foto
    elif foto.startswith('/'):
        return foto
    elif foto.startswith('uploads/'):
        return f'/static/{foto}'
    else:
        return f'{prefijo}{foto}'


# Redirect de /api/chat/ a /chat/ (interfaz web)
@bp_chat.route('/')
@bp_chat.route('')
def redirigir_a_interfaz():
    """Redirige a la interfaz web del chat."""
    from flask import redirect
    return redirect('/chat/')


def obtener_servicio_chat() -> ServicioChat:
    """
    Obtiene el servicio de chat para la request actual.

    Returns:
        ServicioChat configurado con la sesion de BD
    """
    if 'servicio_chat' not in g:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session

        g.servicio_chat = ServicioChat(
            repo_conversacion=RepositorioConversacionPostgreSQL(db_session),
            repo_participante=RepositorioParticipantePostgreSQL(db_session),
            repo_mensaje=RepositorioMensajePostgreSQL(db_session),
            repo_archivo=RepositorioArchivoMensajePostgreSQL(db_session),
            repo_reaccion=RepositorioReaccionPostgreSQL(db_session),
            repo_presencia=RepositorioPresenciaPostgreSQL(db_session),
            repo_bloqueo=RepositorioBloqueoPostgreSQL(db_session),
            repo_indicador=RepositorioIndicadorAccionPostgreSQL(db_session)
        )
    return g.servicio_chat


@bp_chat.teardown_request
def cerrar_session_chat(exception=None):
    """Cierra la sesion de BD al finalizar la request."""
    db_session = g.pop('db_session_chat', None)
    if db_session:
        if exception:
            print(f"[DEBUG-TEARDOWN] Rollback por excepción: {exception}")
            db_session.rollback()
        else:
            try:
                db_session.commit()
                print("[DEBUG-TEARDOWN] Commit exitoso")
            except Exception as e:
                print(f"[DEBUG-TEARDOWN] ERROR en commit: {e}")
                db_session.rollback()
        db_session.close()


def requiere_autenticacion(f):
    """Decorador que verifica que el usuario este autenticado."""
    @wraps(f)
    def decorador(*args, **kwargs):
        # Verificar autenticación por session o por Flask-Login
        from flask_login import current_user
        if 'usuario_id' not in session and not (current_user and current_user.is_authenticated):
            return jsonify({
                'exito': False,
                'mensaje': 'No autenticado'
            }), 401
        return f(*args, **kwargs)
    return decorador


def obtener_usuario_id() -> int:
    """Obtiene el ID del usuario actual."""
    from flask_login import current_user
    # Primero intentar con session, luego con Flask-Login
    if 'usuario_id' in session:
        uid = session.get('usuario_id')
        return int(uid) if uid is not None else None
    if current_user and current_user.is_authenticated:
        uid = current_user.id
        return int(uid) if uid is not None else None
    return None


# =============================================================================
# CONVERSACIONES
# =============================================================================

@bp_chat.route('/conversations', methods=['GET'])
@bp_chat.route('/conversaciones', methods=['GET'])  # Alias español
@requiere_autenticacion
def obtener_conversaciones():
    """
    Obtiene las conversaciones del usuario.

    Query params:
        limit: int (default 20)
        offset: int (default 0)

    Response:
        {
            "success": true,
            "conversations": [...]
        }
    """
    try:
        limite = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        usuario_actual = obtener_usuario_id()

        servicio = obtener_servicio_chat()
        conversaciones = servicio.obtener_conversaciones(
            usuario_actual, limite, offset
        )

        # Obtener info de usuarios para conversaciones directas
        # IMPORTANTE: Reutilizar la sesión del servicio para evitar agotar el pool
        from infraestructura.persistencia.modelos.modelo_usuario import ModeloUsuario
        db_session = g.get('db_session_chat')
        if not db_session:
            gestor = obtener_gestor()
            db_session = gestor.session()
            g.db_session_chat = db_session

        try:
            # Recolectar IDs de usuarios de los participantes
            user_ids = set()
            for c in conversaciones:
                participantes = getattr(c, 'participantes', None) or []
                for p in participantes:
                    # Participantes pueden ser dict o objeto
                    p_id = p.get('usuario_id') if isinstance(p, dict) else getattr(p, 'usuario_id', None)
                    if p_id:
                        user_ids.add(p_id)

            # Obtener info de usuarios con fallback a foto de trabajador
            usuarios_info = {}
            presencias = {}
            if user_ids:
                # Query con subquery para obtener foto del trabajador
                from sqlalchemy import text
                query_usuarios = text("""
                    SELECT u.id, u.username, u.email, u.full_name, u.role,
                           u.profile_picture, t.foto_perfil as foto_trabajador
                    FROM usuarios u
                    LEFT JOIN trabajadores t ON u.trabajador_id = t.id
                    WHERE u.id = ANY(:user_ids)
                """)
                result = db_session.execute(query_usuarios, {'user_ids': list(user_ids)})
                usuarios_data = result.fetchall()

                # Obtener presencia de todos los usuarios
                presencias = servicio.obtener_presencia(list(user_ids))

                for row in usuarios_data:
                    u_id = row[0]
                    username = row[1]
                    email = row[2]
                    full_name = row[3]
                    role = row[4]
                    profile_picture = row[5]
                    foto_trabajador = row[6]

                    # Obtener presencia del usuario
                    user_presencia = presencias.get(u_id, {'online': False, 'last_seen': None})

                    # 2026-06-12: los master tambien aparecen con su nombre real
                    # (antes se enmascaraban como "Fundación Maquita")
                    # Usar helper con fallback a foto de trabajador
                    foto_url = obtener_foto_usuario_con_fallback(profile_picture, foto_trabajador)

                    usuarios_info[u_id] = {
                        'id': u_id,
                        'nombre': full_name or username or email,
                        'foto': foto_url,
                        'email': email,
                        'online': user_presencia.get('online', False),
                        'last_seen': user_presencia.get('last_seen'),
                        'is_institutional': False
                    }

            # Convertir a formato esperado por frontend
            conv_list = []
            for c in conversaciones:
                conv_dict = c.__dict__.copy() if hasattr(c, '__dict__') else dict(c)
                # Mapear campos para compatibilidad
                conv_dict['conversation_type'] = conv_dict.get('tipo', 'direct')
                conv_dict['unread_count'] = conv_dict.get('mensajes_no_leidos', 0)
                # Mapear ultimo_mensaje_preview a last_message para frontend
                conv_dict['last_message'] = conv_dict.get('ultimo_mensaje_preview', '')
                conv_dict['last_message_preview'] = conv_dict.get('ultimo_mensaje_preview', '')

                # Para conversaciones directas, obtener info del otro usuario
                if conv_dict.get('tipo') == 'direct' or conv_dict.get('conversation_type') == 'direct':
                    participantes = getattr(c, 'participantes', None) or []
                    for p in participantes:
                        # Participantes pueden ser dict o objeto
                        p_id = p.get('usuario_id') if isinstance(p, dict) else getattr(p, 'usuario_id', None)
                        if p_id and p_id != usuario_actual and p_id in usuarios_info:
                            otro_usuario = usuarios_info[p_id]
                            # Formato español
                            conv_dict['nombre'] = otro_usuario['nombre']
                            conv_dict['display_name'] = otro_usuario['nombre']
                            conv_dict['avatar'] = otro_usuario['foto']
                            conv_dict['otro_usuario'] = otro_usuario
                            # Formato inglés para compatibilidad con frontend
                            conv_dict['name'] = otro_usuario['nombre']
                            conv_dict['other_user'] = {
                                'id': otro_usuario['id'],
                                'name': otro_usuario['nombre'],
                                'photo': otro_usuario['foto'],
                                'email': otro_usuario['email'],
                                'online': otro_usuario.get('online', False),
                                'last_seen': otro_usuario.get('last_seen')
                            }
                            break

                conv_list.append(conv_dict)

        finally:
            # No cerrar aquí - se cierra en teardown_request
            pass

        # Conversaciones archivadas: ?archivadas=1 muestra SOLO archivadas; por defecto las excluye
        try:
            from sqlalchemy import text as _t
            solo_archivadas = request.args.get('archivadas') in ('1', 'true', 'True')
            arch = db_session.execute(_t(
                "SELECT conversation_id FROM chat_participants "
                "WHERE user_id = :u AND is_archived = TRUE AND is_active = TRUE"
            ), {'u': usuario_actual}).fetchall()
            arch_ids = {r[0] for r in arch}
            if solo_archivadas:
                conv_list = [c for c in conv_list if c.get('id') in arch_ids]
            elif arch_ids:
                conv_list = [c for c in conv_list if c.get('id') not in arch_ids]
        except Exception:
            pass

        return jsonify({
            'success': True,
            'exito': True,
            'conversations': conv_list,
            'conversaciones': conv_list
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'exito': False,
            'error': 'Error interno del servidor',
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/conversations/<int:conversacion_id>', methods=['GET'])
@bp_chat.route('/conversaciones/<int:conversacion_id>', methods=['GET'])  # Alias español
@requiere_autenticacion
def obtener_conversacion(conversacion_id: int):
    """
    Obtiene una conversacion por ID.

    Response:
        {
            "exito": true,
            "conversacion": {...}
        }
    """
    try:
        servicio = obtener_servicio_chat()
        conversacion = servicio.obtener_conversacion(
            conversacion_id, obtener_usuario_id()
        )

        if not conversacion:
            return jsonify({
                'exito': False,
                'mensaje': 'Conversacion no encontrada'
            }), 404

        return jsonify({
            'exito': True,
            'conversacion': conversacion.__dict__
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/conversations/direct', methods=['POST'])
@bp_chat.route('/conversaciones/directa', methods=['POST'])  # Alias español
@requiere_autenticacion
def crear_conversacion_directa():
    """
    Crea o recupera una conversacion directa.

    Request:
        {
            "usuario_id": int
        }

    Response:
        {
            "exito": true,
            "conversacion": {...}
        }
    """
    try:
        datos = request.get_json()
        print(f"[DEBUG] crear_conversacion_directa - datos recibidos: {datos}")

        # Aceptar usuario_id o user_id para compatibilidad
        otro_usuario_id = datos.get('usuario_id') or datos.get('user_id') if datos else None
        if not otro_usuario_id:
            return jsonify({
                'exito': False,
                'success': False,
                'mensaje': 'usuario_id o user_id es requerido'
            }), 400

        otro_usuario_id = int(otro_usuario_id)
        usuario_actual = obtener_usuario_id()
        print(f"[DEBUG] crear_conversacion_directa - usuario_actual={usuario_actual}, otro_usuario_id={otro_usuario_id}")

        if otro_usuario_id == usuario_actual:
            return jsonify({
                'exito': False,
                'success': False,
                'mensaje': 'No puedes chatear contigo mismo'
            }), 400

        # Aislamiento por dominio (multi-empresa)
        try:
            import tenant_chat as _tc
            if _tc.aislamiento_activo():
                _db = g.get('db_session_chat')
                if not _db:
                    from infraestructura.base_datos.base import obtener_gestor as _og
                    _db = _og().session(); g.db_session_chat = _db
                if _tc.primer_bloqueado(_db, usuario_actual, [otro_usuario_id]) is not None:
                    return jsonify({'exito': False, 'success': False, 'mensaje': 'No puedes chatear con usuarios de otra organizacion'}), 403
        except Exception:
            pass
        servicio = obtener_servicio_chat()
        resultado = servicio.crear_conversacion_directa(
            usuario_actual,
            otro_usuario_id
        )
        print(f"[DEBUG] crear_conversacion_directa - resultado: exito={resultado.exito}, mensaje={resultado.mensaje}")

        status = 200 if resultado.exito else 400

        # Formatear respuesta para compatibilidad con frontend
        response = {
            'exito': resultado.exito,
            'success': resultado.exito,
            'mensaje': resultado.mensaje
        }

        # Extraer conversacion de datos si existe
        if resultado.datos and 'conversacion' in resultado.datos:
            conv = resultado.datos['conversacion']
            response['conversation'] = conv
            response['conversacion'] = conv
            response['datos'] = resultado.datos

        return jsonify(response), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        error_detalle = str(e)
        print(f"[ERROR] crear_conversacion_directa - {error_detalle}")
        return jsonify({
            'exito': False,
            'success': False,
            'mensaje': f'Error interno del servidor: {error_detalle}'
        }), 500


@bp_chat.route('/conversations/group', methods=['POST'])
@requiere_autenticacion
def crear_grupo():
    """
    Crea un grupo de chat.

    Request:
        {
            "nombre": "Nombre del grupo",
            "miembros": [1, 2, 3],
            "descripcion": "opcional"
        }

    Response:
        {
            "exito": true,
            "conversacion": {...}
        }
    """
    try:
        datos = request.get_json() or {}
        # Aceptar claves en espanol o ingles (el frontend usa name/participant_ids)
        nombre = (datos.get('nombre') or datos.get('name') or '').strip()
        if not nombre:
            return jsonify({
                'exito': False, 'success': False,
                'mensaje': 'nombre es requerido', 'error': 'nombre es requerido'
            }), 400

        miembros = (datos.get('miembros') or datos.get('participant_ids')
                    or datos.get('members') or datos.get('miembros_ids') or [])
        if not isinstance(miembros, list):
            miembros = []
        descripcion = datos.get('descripcion') or datos.get('description')

        # Aislamiento por dominio (multi-empresa)
        try:
            import tenant_chat as _tc
            if _tc.aislamiento_activo() and miembros:
                _db = g.get('db_session_chat')
                if not _db:
                    from infraestructura.base_datos.base import obtener_gestor as _og
                    _db = _og().session(); g.db_session_chat = _db
                _mids = [int(m) for m in miembros if str(m).isdigit()]
                if _tc.primer_bloqueado(_db, obtener_usuario_id(), _mids) is not None:
                    return jsonify({'exito': False, 'success': False, 'mensaje': 'No puedes agregar usuarios de otra organizacion al grupo'}), 403
        except Exception:
            pass
        servicio = obtener_servicio_chat()
        resultado = servicio.crear_grupo(
            creador_id=obtener_usuario_id(),
            nombre=nombre,
            miembros_ids=miembros,
            descripcion=descripcion
        )

        status = 200 if resultado.exito else 400
        # Extraer la conversacion para el frontend (espera data.conversation.id)
        conv = None
        if resultado.exito and resultado.datos:
            conv = (resultado.datos.get('conversacion') or resultado.datos.get('conversation'))
        return jsonify({
            'exito': resultado.exito,
            'success': resultado.exito,
            'mensaje': resultado.mensaje,
            'error': None if resultado.exito else resultado.mensaje,
            'datos': resultado.datos,
            'conversation': conv,
            'conversacion': conv
        }), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


# =============================================================================
# MENSAJES
# =============================================================================

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


@bp_chat.route('/conversations/<int:conversacion_id>/messages', methods=['POST'])
@bp_chat.route('/conversaciones/<int:conversacion_id>/mensajes', methods=['POST'])  # Alias español
@requiere_autenticacion
def enviar_mensaje(conversacion_id: int):
    """
    Envia un mensaje a una conversacion.

    Request:
        {
            "contenido": "texto del mensaje",
            "tipo": "text" (opcional),
            "respuesta_a": int (opcional)
        }

    Response:
        {
            "exito": true,
            "mensaje": {...}
        }
    """
    try:
        # Soportar tanto JSON como multipart/form-data (para archivos)
        if request.content_type and 'multipart/form-data' in request.content_type:
            datos = {
                'contenido': request.form.get('content', '') or request.form.get('contenido', ''),
                'tipo': request.form.get('message_type', 'document') or request.form.get('tipo', 'document'),
            }
            archivos = request.files.getlist('files')
        else:
            datos = request.get_json()
            archivos = []

        if not datos:
            return jsonify({
                'exito': False,
                'mensaje': 'Datos no proporcionados'
            }), 400

        # Si hay archivos adjuntos, guardarlos y enviar mensaje con media
        if archivos:
            import os
            from werkzeug.utils import secure_filename
            usuario_id = obtener_usuario_id()
            tipo_mensaje = datos.get('tipo', 'document')
            contenido = datos.get('contenido', '').strip()

            # Guardar en ruta servida por Nginx: /uploads/ -> interfaces/web/estaticos/uploads/
            base_upload = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'web', 'estaticos', 'uploads', 'chat', str(conversacion_id)
            )
            os.makedirs(base_upload, exist_ok=True)

            archivos_para_servicio = []
            media_list = []
            for archivo in archivos:
                if archivo and archivo.filename:
                    filename = secure_filename(archivo.filename)
                    import time
                    ts = int(time.time())
                    filename = f"{ts}_{filename}"
                    filepath = os.path.join(base_upload, filename)
                    archivo.save(filepath)

                    # Determinar tipo de media. PRIORIDAD: el tipo que indica el
                    # cliente (mensaje_type) y el MIME; la extension es ultimo recurso.
                    # (Evita que un audio de voz .webm se clasifique como video, o un
                    #  gif como imagen generica.)
                    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
                    mime = (archivo.content_type or '').lower()
                    tipo_cliente = (tipo_mensaje or '').lower()

                    if tipo_cliente in ('audio', 'voice') or mime.startswith('audio/'):
                        media_type = 'audio'
                    elif tipo_cliente == 'gif' or ext == 'gif':
                        media_type = 'image'  # los gif se muestran como imagen animada
                    elif tipo_cliente == 'image' or mime.startswith('image/') or ext in ('jpg', 'jpeg', 'png', 'webp', 'bmp'):
                        media_type = 'image'
                    elif tipo_cliente == 'video' or mime.startswith('video/') or ext in ('mp4', 'mov', 'avi', 'mkv'):
                        media_type = 'video'
                    elif ext == 'webm':
                        # webm sin pista clara: si el cliente no dijo video, tratar como audio
                        media_type = 'video' if tipo_cliente == 'video' else 'audio'
                    elif ext in ('mp3', 'ogg', 'wav', 'aac', 'm4a', 'opus'):
                        media_type = 'audio'
                    else:
                        media_type = 'document'
                    # El tipo del MENSAJE sigue al del primer archivo (coherencia UI)
                    tipo_mensaje = media_type

                    # URL pública servida por Nginx
                    url_publica = f'/uploads/chat/{conversacion_id}/{filename}'
                    tipo_mime = archivo.content_type or 'application/octet-stream'
                    file_size = os.path.getsize(filepath)

                    archivos_para_servicio.append({
                        'ruta': url_publica,
                        'nombre': archivo.filename,
                        'tamanio': file_size,
                        'tipo_mime': tipo_mime
                    })
                    media_list.append({
                        'file_path': url_publica,
                        'file_name': archivo.filename,
                        'media_type': media_type,
                        'file_size': file_size,
                        'mime_type': tipo_mime
                    })

            # Usar enviar_mensaje_con_archivos para crear registros en chat_message_media
            servicio = obtener_servicio_chat()
            resultado = servicio.enviar_mensaje_con_archivos(
                conversacion_id=conversacion_id,
                remitente_id=usuario_id,
                archivos=archivos_para_servicio,
                tipo_media=tipo_mensaje,
                contenido=contenido or None
            )

            if resultado.exito and resultado.datos:
                mensaje_data = resultado.datos.get('mensaje', {})
                mensaje_data['remitente'] = {
                    'id': usuario_id,
                    'nombre': session.get('usuario_nombre', 'Usuario')
                }
                mensaje_data['archivos'] = media_list
                emitir_mensaje_nuevo(conversacion_id, mensaje_data)

            response_data = {
                'exito': resultado.exito,
                'success': resultado.exito,
                'mensaje': resultado.mensaje
            }
            if resultado.datos and resultado.datos.get('mensaje'):
                msg = resultado.datos['mensaje']
                response_data['message'] = {
                    'id': msg.get('id'),
                    'content': msg.get('contenido'),
                    'message_type': tipo_mensaje,
                    'sender_id': usuario_id,
                    'created_at': msg.get('creado_en'),
                    'is_own_message': True,
                    'media': media_list
                }
            return jsonify(response_data), 200 if resultado.exito else 400

        # Aceptar 'contenido' o 'content' para compatibilidad con frontend
        contenido = (datos.get('contenido') or datos.get('content', '')).strip()
        tipo_mensaje = datos.get('tipo') or datos.get('message_type', 'text')
        gif_url = datos.get('gif_url') or datos.get('url')

        # Si es un GIF, usar el servicio de GIF
        if tipo_mensaje == 'gif' and gif_url:
            servicio = obtener_servicio_chat()
            usuario_id = obtener_usuario_id()
            resultado = servicio.enviar_gif(
                conversacion_id=conversacion_id,
                remitente_id=usuario_id,
                url_gif=gif_url,
                contenido=contenido or 'GIF'
            )

            if resultado.exito and resultado.datos:
                mensaje_data = resultado.datos.get('mensaje', {})
                mensaje_data['remitente'] = {
                    'id': usuario_id,
                    'nombre': session.get('usuario_nombre', 'Usuario')
                }
                print(f"[DEBUG-GIF] Enviando GIF via WebSocket:")
                print(f"[DEBUG-GIF]   tipo: {mensaje_data.get('tipo')}")
                print(f"[DEBUG-GIF]   gif_url: {mensaje_data.get('gif_url')}")
                print(f"[DEBUG-GIF]   remitente_id: {mensaje_data.get('remitente_id')}")
                print(f"[DEBUG-GIF]   conversacion_id: {conversacion_id}")
                emitir_mensaje_nuevo(conversacion_id, mensaje_data)

            status = 200 if resultado.exito else 400

            # Respuesta compatible con frontend
            response_data = {
                'exito': resultado.exito,
                'success': resultado.exito,
                'mensaje': resultado.mensaje
            }

            if resultado.datos and resultado.datos.get('mensaje'):
                msg = resultado.datos['mensaje']
                response_data['message'] = {
                    'id': msg.get('id'),
                    'content': msg.get('contenido'),
                    'message_type': 'gif',
                    'sender_id': usuario_id,
                    'created_at': msg.get('creado_en'),
                    'is_own_message': True,
                    'media': [{
                        'file_path': gif_url,
                        'media_type': 'gif'
                    }]
                }
                response_data['datos'] = resultado.datos

            return jsonify(response_data), status

        if not contenido:
            return jsonify({
                'exito': False,
                'success': False,
                'mensaje': 'El contenido es requerido'
            }), 400

        servicio = obtener_servicio_chat()
        usuario_id = obtener_usuario_id()
        resultado = servicio.enviar_mensaje(
            conversacion_id=conversacion_id,
            remitente_id=usuario_id,
            contenido=contenido,
            tipo=tipo_mensaje,
            respuesta_a_id=datos.get('respuesta_a') or datos.get('reply_to_id')
        )

        # Emitir via WebSocket si fue exitoso
        if resultado.exito and resultado.datos:
            mensaje_data = resultado.datos.get('mensaje', {})
            mensaje_data['remitente'] = {
                'id': usuario_id,
                'nombre': session.get('usuario_nombre', 'Usuario')
            }
            emitir_mensaje_nuevo(conversacion_id, mensaje_data)

        status = 200 if resultado.exito else 400

        # Respuesta compatible con frontend (success + message)
        response_data = {
            'exito': resultado.exito,
            'success': resultado.exito,
            'mensaje': resultado.mensaje
        }

        # Incluir mensaje enviado en formato compatible
        if resultado.datos and resultado.datos.get('mensaje'):
            msg = resultado.datos['mensaje']
            response_data['message'] = {
                'id': msg.get('id'),
                'content': msg.get('contenido'),
                'message_type': msg.get('tipo', 'text'),
                'sender_id': usuario_id,
                'created_at': msg.get('creado_en'),
                'is_own_message': True
            }
            response_data['datos'] = resultado.datos

        return jsonify(response_data), status

    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error enviando mensaje: {e}")
        traceback.print_exc()

        # Intentar hacer rollback manual si hay sesion
        db_session = g.get('db_session_chat')
        if db_session:
            try:
                db_session.rollback()
            except:
                pass

        return jsonify({
            'exito': False,
            'success': False,
            'mensaje': f'Error interno del servidor: {str(e)}'
        }), 500


@bp_chat.route('/messages/<int:mensaje_id>', methods=['PUT'])
@requiere_autenticacion
def editar_mensaje(mensaje_id: int):
    """
    Edita un mensaje existente.

    Request:
        {
            "contenido": "nuevo texto"
        }

    Response:
        {
            "exito": true,
            "mensaje": {...}
        }
    """
    try:
        datos = request.get_json()
        if not datos or 'contenido' not in datos:
            return jsonify({
                'exito': False,
                'mensaje': 'contenido es requerido'
            }), 400

        servicio = obtener_servicio_chat()
        resultado = servicio.editar_mensaje(
            mensaje_id=mensaje_id,
            usuario_id=obtener_usuario_id(),
            nuevo_contenido=datos['contenido']
        )

        # Emitir via WebSocket si fue exitoso
        if resultado.exito and resultado.datos:
            mensaje_data = resultado.datos.get('mensaje', {})
            conversacion_id = mensaje_data.get('conversacion_id')
            nuevo_texto = mensaje_data.get('contenido') or datos.get('contenido') or datos.get('content') or ''
            if conversacion_id:
                emitir_a_conversacion(conversacion_id, 'message_edited', mensaje_data)
                # Si el mensaje editado es el ULTIMO de la conversacion, actualizar la
                # previsualizacion de la bandeja (y avisar para refrescar el listado).
                try:
                    from sqlalchemy import text as _t
                    ses = g.get('db_session_chat')
                    if not ses:
                        ses = obtener_gestor().session(); g.db_session_chat = ses
                    res = ses.execute(_t("""
                        UPDATE chat_conversations c
                        SET last_message_preview = :prev, updated_at = NOW()
                        WHERE c.id = :conv
                          AND :mid = (SELECT id FROM chat_messages
                                      WHERE conversation_id = :conv AND is_deleted = false
                                      ORDER BY created_at DESC, id DESC LIMIT 1)
                    """), {'prev': (nuevo_texto or '')[:100], 'conv': conversacion_id, 'mid': mensaje_id})
                    ses.commit()
                    if res.rowcount:
                        emitir_a_conversacion(conversacion_id, 'conversation_preview', {
                            'conversation_id': conversacion_id,
                            'preview': (nuevo_texto or '')[:100]
                        })
                except Exception:
                    pass

        status = 200 if resultado.exito else 400
        return jsonify({
            'exito': resultado.exito,
            'mensaje': resultado.mensaje,
            'datos': resultado.datos
        }), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/messages/<int:mensaje_id>', methods=['DELETE'])
@requiere_autenticacion
def eliminar_mensaje(mensaje_id: int):
    """
    Elimina un mensaje.

    Query params:
        para_todos: bool (default false)
        conversation_id: int (opcional, para notificacion WebSocket)

    Response:
        {
            "exito": true,
            "mensaje": "Mensaje eliminado"
        }
    """
    try:
        para_todos = (request.args.get('para_todos', 'false').lower() == 'true'
                      or request.args.get('for_everyone', 'false').lower() == 'true')
        conversacion_id = request.args.get('conversation_id', type=int)
        usuario_id = obtener_usuario_id()

        servicio = obtener_servicio_chat()
        resultado = servicio.eliminar_mensaje(
            mensaje_id=mensaje_id,
            usuario_id=usuario_id,
            para_todos=para_todos
        )

        # Emitir via WebSocket si fue exitoso
        if resultado.exito and conversacion_id:
            from datetime import timezone as _tz
            emitir_a_conversacion(conversacion_id, 'message_deleted', {
                'message_id': mensaje_id,
                'deleted_by': usuario_id,
                'for_all': para_todos,
                'timestamp': datetime.now(_tz.utc).isoformat()
            })

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


@bp_chat.route('/conversations/<int:conversacion_id>/clear', methods=['DELETE'])
@requiere_autenticacion
def limpiar_conversacion(conversacion_id: int):
    """
    Elimina todos los mensajes de una conversacion (para el usuario actual).
    """
    try:
        usuario_id = obtener_usuario_id()

        from datetime import timezone as _tz
        from sqlalchemy import text as _t

        # Obtener sesion
        db_session = g.get('db_session_chat')
        if not db_session:
            from infraestructura.base_datos.base import obtener_gestor
            gestor = obtener_gestor()
            db_session = gestor.session()
            g.db_session_chat = db_session

        # C-9: quien llama debe ser participante de la conversacion antes de operar
        es_miembro = db_session.execute(_t(
            "SELECT 1 FROM chat_participants WHERE conversation_id = :c AND user_id = :u LIMIT 1"
        ), {"c": conversacion_id, "u": usuario_id}).fetchone()
        if not es_miembro:
            return jsonify({'success': False, 'exito': False,
                            'mensaje': 'No autorizado'}), 403

        from modulos.chat.infraestructura.persistencia.modelos.modelo_mensaje import ModeloMensaje
        mensajes = db_session.query(ModeloMensaje).filter_by(
            conversation_id=conversacion_id,
            is_deleted=False
        ).all()

        count = 0
        ahora = datetime.now(_tz.utc)
        for msg in mensajes:
            msg.is_deleted = True
            msg.deleted_at = ahora
            # Solo borrar para el usuario que lo solicita, no para la otra parte
            msg.deleted_for_everyone = False
            count += 1

        db_session.flush()

        return jsonify({
            'success': True,
            'exito': True,
            'mensaje': f'{count} mensajes eliminados',
            'count': count
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'exito': False,
            'mensaje': 'Error al limpiar conversacion'
        }), 500


@bp_chat.route('/conversations/<int:conversacion_id>/read', methods=['POST'])
@requiere_autenticacion
def marcar_leido(conversacion_id: int):
    """
    Marca mensajes como leidos.

    Request (opcional):
        {
            "hasta_mensaje_id": int
        }

    Response:
        {
            "exito": true,
            "mensaje": "Marcado como leido"
        }
    """
    try:
        # Usar silent=True para evitar error si no hay JSON
        datos = request.get_json(silent=True) or {}
        hasta_mensaje_id = datos.get('hasta_mensaje_id')

        servicio = obtener_servicio_chat()
        resultado = servicio.marcar_leido(
            conversacion_id=conversacion_id,
            usuario_id=obtener_usuario_id(),
            hasta_mensaje_id=hasta_mensaje_id
        )

        # Avisar a los DEMAS participantes (vistos azules en tiempo real).
        # Se emite a los rooms user_<id> de los otros, NO al lector (si no,
        # el lector marcaria como leidos sus propios mensajes enviados).
        if resultado.exito:
            try:
                from sqlalchemy import text as _text
                db_session = g.get('db_session_chat')
                if not db_session:
                    gestor = obtener_gestor()
                    db_session = gestor.session()
                    g.db_session_chat = db_session
                otros = db_session.execute(_text(
                    "SELECT user_id FROM chat_participants "
                    "WHERE conversation_id = :c AND user_id <> :u AND is_active = TRUE"
                ), {'c': conversacion_id, 'u': obtener_usuario_id()}).fetchall()
                from interfaces.websocket import manejador_websocket as _ws
                if _ws.socketio:
                    payload = {
                        'conversation_id': conversacion_id,
                        'hasta_mensaje_id': hasta_mensaje_id,
                        'reader_id': obtener_usuario_id()
                    }
                    for fila in otros:
                        _ws.socketio.emit('messages_read', payload, room=f"user_{fila[0]}")
            except Exception:
                pass

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


# =============================================================================
# MENSAJES CON ARCHIVOS Y MULTIMEDIA
# =============================================================================

@bp_chat.route('/conversations/<int:conversacion_id>/messages/upload', methods=['POST'])
@requiere_autenticacion
def enviar_mensaje_con_archivos(conversacion_id: int):
    """
    Envia un mensaje con archivos multimedia.

    Form data:
        files: Archivos a subir (multipart)
        tipo: Tipo de media (image, video, audio, document)
        contenido: Texto opcional del mensaje

    Response:
        {
            "exito": true,
            "mensaje": {...}
        }
    """
    import os
    from werkzeug.utils import secure_filename

    try:
        # Obtener archivos - soportar ambos nombres: 'files' y 'file'
        archivos = []
        if 'files' in request.files:
            archivos = request.files.getlist('files')
        elif 'file' in request.files:
            archivos = [request.files['file']]

        if not archivos or (len(archivos) == 1 and archivos[0].filename == ''):
            return jsonify({
                'exito': False,
                'success': False,
                'mensaje': 'No se enviaron archivos',
                'error': 'No se enviaron archivos'
            }), 400

        # Soportar ambos nombres: 'tipo' y 'message_type'
        tipo_media = request.form.get('tipo') or request.form.get('message_type', 'document')
        contenido = request.form.get('contenido', '').strip() or request.form.get('content', '').strip() or None

        # Directorio de uploads
        upload_dir = os.path.join('static', 'uploads', 'chat', str(conversacion_id))
        os.makedirs(upload_dir, exist_ok=True)

        archivos_data = []
        for archivo in archivos:
            if archivo.filename:
                nombre_seguro = secure_filename(archivo.filename)
                # Agregar timestamp para evitar colisiones
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                nombre_final = timestamp + nombre_seguro
                ruta = os.path.join(upload_dir, nombre_final)

                # Guardar archivo
                archivo.save(ruta)

                # Obtener info del archivo
                tamanio = os.path.getsize(ruta)
                tipo_mime = archivo.content_type or 'application/octet-stream'

                archivos_data.append({
                    'ruta': ruta.replace('\\', '/'),
                    'nombre': archivo.filename,
                    'tamanio': tamanio,
                    'tipo_mime': tipo_mime
                })

        servicio = obtener_servicio_chat()
        usuario_id = obtener_usuario_id()
        resultado = servicio.enviar_mensaje_con_archivos(
            conversacion_id=conversacion_id,
            remitente_id=usuario_id,
            archivos=archivos_data,
            tipo_media=tipo_media,
            contenido=contenido
        )

        status = 200 if resultado.exito else 400

        # Preparar respuesta compatible con frontend
        response_data = {
            'exito': resultado.exito,
            'success': resultado.exito,
            'mensaje': resultado.mensaje,
            'datos': resultado.datos
        }

        # Incluir mensaje en formato esperado por frontend
        if resultado.datos and resultado.datos.get('mensaje'):
            msg = resultado.datos['mensaje']
            response_data['message'] = {
                'id': msg.get('id'),
                'content': msg.get('contenido'),
                'message_type': tipo_media,
                'sender_id': usuario_id,
                'created_at': msg.get('creado_en'),
                'is_own_message': True,
                'media': [
                    {
                        'file_path': a.get('ruta'),
                        'media_type': tipo_media,
                        'file_name': a.get('nombre'),
                        'file_size': a.get('tamanio')
                    }
                    for a in msg.get('archivos', [])
                ]
            }

            # Emitir via WebSocket para tiempo real
            mensaje_data = msg.copy()
            mensaje_data['remitente'] = {
                'id': usuario_id,
                'nombre': session.get('usuario_nombre', 'Usuario')
            }
            emitir_mensaje_nuevo(conversacion_id, mensaje_data)

        return jsonify(response_data), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/conversations/<int:conversacion_id>/messages/location', methods=['POST'])
@requiere_autenticacion
def enviar_ubicacion(conversacion_id: int):
    """
    Envia un mensaje con ubicacion.

    Request:
        {
            "latitud": float,
            "longitud": float,
            "nombre": "Nombre del lugar" (opcional),
            "direccion": "Direccion" (opcional)
        }

    Response:
        {
            "exito": true,
            "mensaje": {...}
        }
    """
    try:
        datos = request.get_json()
        if not datos:
            return jsonify({
                'exito': False,
                'mensaje': 'Datos no proporcionados'
            }), 400

        if 'latitud' not in datos or 'longitud' not in datos:
            return jsonify({
                'exito': False,
                'mensaje': 'latitud y longitud son requeridos'
            }), 400

        servicio = obtener_servicio_chat()
        resultado = servicio.enviar_ubicacion(
            conversacion_id=conversacion_id,
            remitente_id=obtener_usuario_id(),
            latitud=float(datos['latitud']),
            longitud=float(datos['longitud']),
            nombre=datos.get('nombre'),
            direccion=datos.get('direccion')
        )

        status = 200 if resultado.exito else 400
        return jsonify({
            'exito': resultado.exito,
            'mensaje': resultado.mensaje,
            'datos': resultado.datos
        }), status

    except ValueError as e:
        return jsonify({
            'exito': False,
            'mensaje': 'Coordenadas invalidas'
        }), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/conversations/<int:conversacion_id>/messages/contact', methods=['POST'])
@requiere_autenticacion
def enviar_contacto(conversacion_id: int):
    """
    Envia un mensaje con informacion de contacto.

    Request:
        {
            "nombre": "Nombre del contacto",
            "telefono": "+593999999999" (opcional si hay email),
            "email": "correo@ejemplo.com" (opcional si hay telefono),
            "organizacion": "Empresa" (opcional),
            "cargo": "Cargo" (opcional)
        }

    Response:
        {
            "exito": true,
            "mensaje": {...}
        }
    """
    try:
        datos = request.get_json()
        if not datos:
            return jsonify({
                'exito': False,
                'mensaje': 'Datos no proporcionados'
            }), 400

        if 'nombre' not in datos:
            return jsonify({
                'exito': False,
                'mensaje': 'nombre es requerido'
            }), 400

        if not datos.get('telefono') and not datos.get('email'):
            return jsonify({
                'exito': False,
                'mensaje': 'Se requiere al menos telefono o email'
            }), 400

        servicio = obtener_servicio_chat()
        resultado = servicio.enviar_contacto(
            conversacion_id=conversacion_id,
            remitente_id=obtener_usuario_id(),
            nombre=datos['nombre'],
            telefono=datos.get('telefono'),
            email=datos.get('email'),
            organizacion=datos.get('organizacion'),
            cargo=datos.get('cargo')
        )

        status = 200 if resultado.exito else 400
        return jsonify({
            'exito': resultado.exito,
            'mensaje': resultado.mensaje,
            'datos': resultado.datos
        }), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/conversations/<int:conversacion_id>/messages/gif', methods=['POST'])
@requiere_autenticacion
def enviar_gif(conversacion_id: int):
    """
    Envia un mensaje con GIF.

    Request:
        {
            "url": "https://media.giphy.com/...",
            "contenido": "Texto opcional"
        }

    Response:
        {
            "exito": true,
            "mensaje": {...}
        }
    """
    try:
        datos = request.get_json()
        if not datos or 'url' not in datos:
            return jsonify({
                'exito': False,
                'mensaje': 'url del GIF es requerida'
            }), 400

        servicio = obtener_servicio_chat()
        resultado = servicio.enviar_gif(
            conversacion_id=conversacion_id,
            remitente_id=obtener_usuario_id(),
            url_gif=datos['url'],
            contenido=datos.get('contenido')
        )

        status = 200 if resultado.exito else 400
        return jsonify({
            'exito': resultado.exito,
            'mensaje': resultado.mensaje,
            'datos': resultado.datos
        }), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


# =============================================================================
# REACCIONES
# =============================================================================

@bp_chat.route('/messages/<int:mensaje_id>/reactions', methods=['GET'])
@requiere_autenticacion
def obtener_reacciones(mensaje_id: int):
    """
    Obtiene las reacciones de un mensaje.

    Response:
        {
            "success": true,
            "reactions": [
                {"emoji": "😀", "count": 2, "user_ids": [1, 2]}
            ]
        }
    """
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.obtener_reacciones_mensaje(mensaje_id)

        if resultado.exito:
            return jsonify({
                'success': True,
                'exito': True,
                'reactions': resultado.datos.get('reacciones', [])
            }), 200
        else:
            return jsonify({
                'success': False,
                'exito': False,
                'reactions': [],
                'mensaje': resultado.mensaje
            }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'exito': False,
            'reactions': [],
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/messages/<int:mensaje_id>/reactions', methods=['POST'])
@requiere_autenticacion
def agregar_reaccion(mensaje_id: int):
    """
    Agrega una reaccion a un mensaje.

    Request:
        {
            "emoji": "..."
        }

    Response:
        {
            "exito": true,
            "mensaje": "Reaccion agregada"
        }
    """
    try:
        datos = request.get_json()
        if not datos or 'emoji' not in datos:
            return jsonify({
                'exito': False,
                'mensaje': 'emoji es requerido'
            }), 400

        servicio = obtener_servicio_chat()
        usuario_id = obtener_usuario_id()
        resultado = servicio.agregar_reaccion(
            mensaje_id=mensaje_id,
            usuario_id=usuario_id,
            emoji=datos['emoji']
        )

        # Si la reaccion se agrego exitosamente, emitir via WebSocket
        if resultado.exito:
            # Obtener el conversacion_id del mensaje
            mensaje = servicio._repo_mensaje.buscar_por_id(mensaje_id)
            if mensaje and mensaje.conversacion_id:
                from datetime import datetime
                emitir_a_conversacion(
                    mensaje.conversacion_id,
                    'reaction_added',
                    {
                        'message_id': mensaje_id,
                        'user_id': usuario_id,
                        'emoji': datos['emoji'],
                        'timestamp': datetime.now().isoformat()
                    }
                )

        status = 200 if resultado.exito else 400
        return jsonify({
            'exito': resultado.exito,
            'success': resultado.exito,  # Alias para compatibilidad con frontend
            'mensaje': resultado.mensaje,
            'reaction': {'emoji': datos['emoji']} if resultado.exito else None
        }), status

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'success': False,
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/messages/<int:mensaje_id>/reactions', methods=['DELETE'])
@requiere_autenticacion
def eliminar_reaccion(mensaje_id: int):
    """
    Elimina la reaccion del usuario a un mensaje.

    Response:
        {
            "exito": true,
            "mensaje": "Reaccion eliminada"
        }
    """
    try:
        servicio = obtener_servicio_chat()
        usuario_id = obtener_usuario_id()

        # Obtener el conversacion_id ANTES de eliminar para poder emitir el evento
        mensaje = servicio._repo_mensaje.buscar_por_id(mensaje_id)
        conversacion_id = mensaje.conversacion_id if mensaje else None

        resultado = servicio.eliminar_reaccion(
            mensaje_id=mensaje_id,
            usuario_id=usuario_id
        )

        # Si la reaccion se elimino exitosamente, emitir via WebSocket
        if resultado.exito and conversacion_id:
            from datetime import datetime
            emitir_a_conversacion(
                conversacion_id,
                'reaction_removed',
                {
                    'message_id': mensaje_id,
                    'user_id': usuario_id,
                    'timestamp': datetime.now().isoformat()
                }
            )

        return jsonify({
            'exito': resultado.exito,
            'success': resultado.exito,  # Alias para compatibilidad con frontend
            'mensaje': resultado.mensaje
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'success': False,
            'mensaje': 'Error interno del servidor'
        }), 500


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
        servicio.actualizar_presencia(obtener_usuario_id(), en_linea)

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


# =============================================================================
# BUSQUEDA
# =============================================================================

@bp_chat.route('/search/users', methods=['GET'])
@bp_chat.route('/users/search', methods=['GET'])  # Alias ingles
@bp_chat.route('/usuarios/buscar', methods=['GET'])  # Alias español
@requiere_autenticacion
def buscar_usuarios():
    """
    Busca usuarios para iniciar conversacion.

    Query params:
        q: string (query de busqueda)
        limit: int (default 20)

    Response:
        {
            "success": true,
            "users": [...]
        }
    """
    try:
        query = request.args.get('q', '').strip()
        limite = request.args.get('limit', 20, type=int)

        if len(query) < 2:
            return jsonify({
                'success': True,
                'exito': True,
                'users': [],
                'usuarios': []
            }), 200

        # Buscar en la tabla de usuarios
        # IMPORTANTE: Reutilizar la sesión del servicio para evitar agotar el pool
        from sqlalchemy import or_
        db_session = g.get('db_session_chat')
        if not db_session:
            from infraestructura.base_datos.base import obtener_gestor
            gestor = obtener_gestor()
            db_session = gestor.session()
            g.db_session_chat = db_session

        try:
            # Buscar usuarios que coincidan con el query
            from infraestructura.persistencia.modelos.modelo_usuario import ModeloUsuario

            usuarios = db_session.query(ModeloUsuario).filter(
                or_(
                    ModeloUsuario.full_name.ilike(f'%{query}%'),
                    ModeloUsuario.username.ilike(f'%{query}%'),
                    ModeloUsuario.email.ilike(f'%{query}%')
                ),
                ModeloUsuario.active == True
            ).limit(limite).all()

            # Excluir al usuario actual y normalizar nombres para usuarios institucionales
            usuario_actual = obtener_usuario_id()
            usuarios_lista = []
            for u in usuarios:
                if u.id != usuario_actual:
                    # 2026-06-12: los master tambien aparecen con su nombre real
                    usuarios_lista.append({
                        'id': u.id,
                        'name': u.full_name or u.username or u.email,
                        'email': u.email,
                        'photo': u.profile_picture,
                        'department': None,
                        'username': u.username,
                        'is_institutional': False
                    })

            # Aislamiento por dominio (multi-empresa): solo gente del mismo tenant
            try:
                import tenant_chat as _tc
                _perm = _tc.dominios_permitidos(_tc.emails_por_ids(db_session, [usuario_actual]).get(usuario_actual))
                if _perm is not None:
                    usuarios_lista = [u for u in usuarios_lista if _tc.dominio(u.get('email')) in _perm]
            except Exception:
                pass

            return jsonify({
                'success': True,
                'exito': True,
                'users': usuarios_lista,
                'usuarios': usuarios_lista
            }), 200

        finally:
            # No cerrar aquí - se cierra en teardown_request
            pass

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'exito': False,
            'error': 'Error interno del servidor',
            'mensaje': 'Error interno del servidor'
        }), 500


@bp_chat.route('/trabajadores/activos', methods=['GET'])
@requiere_autenticacion
def obtener_trabajadores_activos():
    """
    Obtiene la lista de trabajadores activos para iniciar chat.

    Query params:
        limit: int (default 30)
        q: string (filtro de búsqueda opcional)

    Response:
        {
            "success": true,
            "trabajadores": [...]
        }
    """
    try:
        limite = request.args.get('limit', 30, type=int)
        query = request.args.get('q', '').strip()
        usuario_actual = obtener_usuario_id()

        from config_nomina import NominaDBConfig
        from sqlalchemy import create_engine, text

        engine = create_engine(NominaDBConfig.NOMINA_DATABASE_URI)

        with engine.connect() as conn:
            # Query para obtener trabajadores activos
            sql = """
                SELECT
                    t.id,
                    t.nombres || ' ' || t.apellidos as nombre_completo,
                    t.foto_perfil,
                    t.email_institucional,
                    c.nombre as cargo,
                    d.nombre as departamento
                FROM trabajadores t
                LEFT JOIN cargos c ON t.cargo_id = c.id
                LEFT JOIN departamentos_empresa d ON t.departamento_id = d.id
                WHERE t.estado = 'ACTIVO'
                AND t.id != :usuario_id
            """

            if query:
                sql += """ AND (
                    LOWER(t.nombres || ' ' || t.apellidos) LIKE LOWER(:query)
                    OR LOWER(t.email_institucional) LIKE LOWER(:query)
                )"""

            sql += " ORDER BY t.nombres, t.apellidos LIMIT :limit"

            params = {
                'usuario_id': usuario_actual,
                'limit': limite
            }
            if query:
                params['query'] = f'%{query}%'

            result = conn.execute(text(sql), params)

            trabajadores = []
            trabajador_ids = []
            for row in result.mappings():
                trabajador_ids.append(row['id'])

                # Construir URL de foto correctamente
                foto_url = None
                if row['foto_perfil']:
                    foto = row['foto_perfil']
                    if foto.startswith(('http://', 'https://')):
                        foto_url = foto
                    elif foto.startswith('/'):
                        foto_url = foto
                    elif foto.startswith('uploads/'):
                        foto_url = f'/static/{foto}'
                    else:
                        # Asumir que es solo el nombre del archivo
                        foto_url = f'/static/uploads/nomina/fotos/{foto}'

                trabajadores.append({
                    'id': row['id'],
                    'name': row['nombre_completo'],
                    'nombre_completo': row['nombre_completo'],
                    'photo': foto_url,
                    'foto_perfil': foto_url,
                    'email': row['email_institucional'],
                    'role': row['cargo'],
                    'department': row['departamento'],
                    'departamento_nombre': row['departamento'],
                    'online': False  # Default, se actualizará abajo
                })

        # Obtener presencia de los trabajadores
        if trabajador_ids:
            servicio = obtener_servicio_chat()
            presencias = servicio.obtener_presencia(trabajador_ids)
            for trab in trabajadores:
                user_presencia = presencias.get(trab['id'], {'online': False})
                trab['online'] = user_presencia.get('online', False)

        return jsonify({
            'success': True,
            'exito': True,
            'trabajadores': trabajadores,
            'users': trabajadores  # Alias para compatibilidad
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'exito': False,
            'error': 'Error interno del servidor'
        }), 500


@bp_chat.route('/unread/count', methods=['GET'])
@requiere_autenticacion
def obtener_no_leidos_total():
    """
    Obtiene el total de mensajes no leidos.

    Response:
        {
            "exito": true,
            "count": int
        }
    """
    try:
        servicio = obtener_servicio_chat()
        # Sumar no leidos de todas las conversaciones
        conversaciones = servicio.obtener_conversaciones(
            obtener_usuario_id(), limite=100
        )
        total = sum(c.mensajes_no_leidos for c in conversaciones)

        return jsonify({
            'exito': True,
            'count': total
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'exito': False,
            'mensaje': 'Error interno del servidor'
        }), 500


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


# =============================================================================
# REENVIO DE MENSAJES (Feature 2)
# =============================================================================

@bp_chat.route('/messages/<int:mensaje_id>/forward', methods=['POST'])
@requiere_autenticacion
def reenviar_mensaje(mensaje_id):
    """
    Reenvia un mensaje a otra conversacion.

    Request:
        { "conversation_id": int }
    """
    try:
        datos = request.get_json()
        conv_destino = datos.get('conversation_id')
        if not conv_destino:
            return jsonify({'success': False, 'mensaje': 'conversation_id requerido'}), 400

        servicio = obtener_servicio_chat()
        resultado = servicio.reenviar_mensaje(mensaje_id, obtener_usuario_id(), conv_destino)

        if resultado.exito and resultado.datos:
            from interfaces.websocket.manejador_websocket import emitir_mensaje_nuevo
            emitir_mensaje_nuevo(conv_destino, resultado.datos.get('mensaje', {}))

        return jsonify({
            'success': resultado.exito,
            'mensaje': resultado.mensaje
        }), 200 if resultado.exito else 400

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'mensaje': 'Error interno'}), 500


# =============================================================================
# MENSAJES FIJADOS (Feature 3)
# =============================================================================

def _conv_de_mensaje(mensaje_id):
    """Devuelve el conversation_id de un mensaje (o None)."""
    try:
        from sqlalchemy import text as _t
        ses = g.get("db_session_chat")
        if not ses:
            ses = obtener_gestor().session(); g.db_session_chat = ses
        fila = ses.execute(_t("SELECT conversation_id FROM chat_messages WHERE id = :id"), {"id": mensaje_id}).fetchone()
        return fila[0] if fila else None
    except Exception:
        return None


@bp_chat.route('/messages/<int:mensaje_id>/pin', methods=['POST'])
@requiere_autenticacion
def fijar_mensaje(mensaje_id):
    """Fija un mensaje en su conversacion."""
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.fijar_mensaje(mensaje_id, obtener_usuario_id())
        if resultado.exito:
            cid = _conv_de_mensaje(mensaje_id)
            if cid:
                try:
                    emitir_a_conversacion(cid, 'message_pinned', {'conversation_id': cid, 'message_id': mensaje_id, 'pinned': True})
                except Exception:
                    pass
        return jsonify({
            'success': resultado.exito,
            'mensaje': resultado.mensaje
        }), 200 if resultado.exito else 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'mensaje': 'Error interno'}), 500


@bp_chat.route('/messages/<int:mensaje_id>/pin', methods=['DELETE'])
@requiere_autenticacion
def desfijar_mensaje(mensaje_id):
    """Desfija un mensaje."""
    try:
        servicio = obtener_servicio_chat()
        cid = _conv_de_mensaje(mensaje_id)
        resultado = servicio.desfijar_mensaje(mensaje_id, obtener_usuario_id())
        if resultado.exito and cid:
            try:
                emitir_a_conversacion(cid, 'message_pinned', {'conversation_id': cid, 'message_id': mensaje_id, 'pinned': False})
            except Exception:
                pass
        return jsonify({
            'success': resultado.exito,
            'mensaje': resultado.mensaje
        }), 200 if resultado.exito else 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'mensaje': 'Error interno'}), 500


@bp_chat.route('/conversations/mark-all-read', methods=['POST'])
@requiere_autenticacion
def marcar_todo_leido():
    """Marca todas las conversaciones como leidas."""
    try:
        usuario_id = obtener_usuario_id()
        servicio = obtener_servicio_chat()
        resultado = servicio.listar_conversaciones(usuario_id)
        if resultado.exito:
            conversaciones = resultado.datos.get('conversaciones', [])
            for conv in conversaciones:
                no_leidos = conv.get('mensajes_no_leidos', 0) or conv.get('unread_count', 0)
                if no_leidos and no_leidos > 0:
                    conv_id = conv.get('id')
                    if conv_id:
                        servicio.marcar_leido(conv_id, usuario_id)
        if hasattr(g, 'db_session_chat') and g.db_session_chat:
            g.db_session_chat.commit()
        return jsonify({'success': True, 'mensaje': 'Todos marcados como leidos'}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'mensaje': 'Error interno'}), 500


@bp_chat.route('/conversations/<int:conversacion_id>/pinned', methods=['GET'])
@requiere_autenticacion
def obtener_mensajes_fijados(conversacion_id):
    """Obtiene los mensajes fijados de una conversacion."""
    try:
        servicio = obtener_servicio_chat()
        resultado = servicio.obtener_mensajes_fijados(conversacion_id, obtener_usuario_id())

        if resultado.exito and resultado.datos:
            # Map to frontend-friendly format
            pinned = []
            for m in resultado.datos.get('pinned', []):
                pinned.append({
                    'id': m.get('id'),
                    'content': m.get('contenido'),
                    'sender_id': m.get('remitente_id'),
                    'created_at': m.get('creado_en'),
                    'message_type': m.get('tipo')
                })
            return jsonify({'success': True, 'pinned': pinned}), 200

        return jsonify({
            'success': resultado.exito,
            'mensaje': resultado.mensaje,
            'pinned': []
        }), 200 if resultado.exito else 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'mensaje': 'Error interno', 'pinned': []}), 500


# =============================================================================
# LLAMADAS EN VIVO - LiveKit (CT 210)
# El cliente pide un token para unirse a la sala de la llamada; la media
# viaja por el SFU LiveKit (wss://datos.maquita.com.ec/livekit).
# Documentacion: (documentacion interna)
# =============================================================================

def _livekit_jwt(api_key: str, api_secret: str, claims: dict) -> str:
    """Genera un JWT HS256 para LiveKit sin dependencias externas."""
    import hmac as _hmac
    import hashlib as _hashlib
    import base64 as _base64
    import json as _json

    def _b64url(datos: bytes) -> bytes:
        return _base64.urlsafe_b64encode(datos).rstrip(b'=')

    cabecera = _b64url(_json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode())
    cuerpo = _b64url(_json.dumps(claims).encode())
    mensaje = cabecera + b'.' + cuerpo
    firma = _b64url(_hmac.new(api_secret.encode(), mensaje, _hashlib.sha256).digest())
    return (mensaje + b'.' + firma).decode()


def _turn_ice_servers():
    """Genera iceServers (STUN+TURN) con credenciales temporales TURN REST
    contra el coturn compartido de Jitsi (CT 201). Devuelve [] si no esta configurado.
    El cliente lo usa SOLO como respaldo (iceTransportPolicy:all): si la conexion
    directa funciona, el TURN no se toca."""
    import os, time, hmac, hashlib, base64
    secret = os.environ.get('LIVEKIT_TURN_SECRET')
    if not secret:
        return []
    udp_host = os.environ.get('LIVEKIT_TURN_UDP_HOST', '179.49.24.167')
    tls_host = os.environ.get('LIVEKIT_TURN_TLS_HOST', 'meet.maquita.com.ec')
    expiry = int(time.time()) + 12 * 3600  # credencial valida 12 h
    username = '%d:livekit' % expiry
    cred = base64.b64encode(
        hmac.new(secret.encode(), username.encode(), hashlib.sha1).digest()
    ).decode()
    return [
        {'urls': 'stun:%s:3478' % udp_host},
        {'urls': 'turn:%s:3478?transport=udp' % udp_host,
         'username': username, 'credential': cred},
        {'urls': 'turns:%s:5349?transport=tcp' % tls_host,
         'username': username, 'credential': cred},
    ]


@bp_chat.route('/llamada/token', methods=['GET'])
@requiere_autenticacion
def obtener_token_llamada():
    """
    Token de acceso a la sala LiveKit de una llamada del chat.

    Query params:
        room: nombre de la sala. Para llamadas 1 a 1 el formato es
              llamada_<idMenor>_<idMayor> y el usuario DEBE ser uno de los dos.

    Returns:
        { exito, url, token, sala, identidad }
    """
    import os
    import re as _re
    import time as _time

    usuario_id = obtener_usuario_id()
    sala = (request.args.get('room') or '').strip()

    if not sala or len(sala) > 100 or not _re.match(r'^[a-zA-Z0-9_\-]+$', sala):
        return jsonify({'exito': False, 'error': 'Sala invalida'}), 400

    # Solo salas de llamada 1 a 1 o de conferencia del chat
    if sala.startswith('llamada_'):
        # 1 a 1: solo los dos participantes pueden pedir token
        partes = sala.split('_')[1:]
        if len(partes) != 2 or str(usuario_id) not in partes:
            return jsonify({'exito': False, 'error': 'No autorizado para esta sala'}), 403
    elif sala.startswith('conf_'):
        # Conferencias: sala efimera con id aleatorio compartido por invitacion
        pass
    else:
        return jsonify({'exito': False, 'error': 'Tipo de sala no permitido'}), 403

    api_key = os.environ.get('LIVEKIT_API_KEY')
    api_secret = os.environ.get('LIVEKIT_API_SECRET')
    ws_url = os.environ.get('LIVEKIT_WS_URL', 'wss://datos.maquita.com.ec/livekit')
    if not api_key or not api_secret:
        return jsonify({'exito': False, 'error': 'LiveKit no configurado'}), 503

    ahora = int(_time.time())
    nombre = session.get('usuario_nombre') or session.get('username') or f'Usuario {usuario_id}'
    token = _livekit_jwt(api_key, api_secret, {
        'iss': api_key,
        'sub': str(usuario_id),
        'name': nombre,
        'nbf': ahora - 10,
        'exp': ahora + 7200,  # 2 horas (duracion maxima de una llamada)
        'video': {
            'room': sala,
            'roomJoin': True,
            'canPublish': True,
            'canSubscribe': True,
        },
    })

    return jsonify({
        'exito': True,
        'url': ws_url,
        'token': token,
        'sala': sala,
        'identidad': str(usuario_id),
        'ice_servers': _turn_ice_servers(),
    })


# =============================================================================
# HISTORIAL DE LLAMADAS (tabla chat_llamadas) + notificacion de perdidas
# Las ventanas de llamada/conferencia registran aqui al finalizar.
# =============================================================================

@bp_chat.route('/llamadas/registrar', methods=['POST'])
@requiere_autenticacion
def registrar_llamada_historial():
    """
    Registra una llamada finalizada (la registra el LLAMANTE / host).

    Body: { room, tipo: audio|video|conferencia, peer_id (opcional en conferencia),
            conversation_id (opcional), estado: completada|sin_respuesta|rechazada,
            duracion: segundos }
    Si la llamada no fue contestada/rechazada, crea notificacion de campanita
    al destinatario ("Llamada perdida de ...").
    """
    from sqlalchemy import text as _text

    usuario_id = obtener_usuario_id()
    datos = request.get_json(silent=True) or {}

    tipo = datos.get('tipo')
    estado = datos.get('estado')
    room = (datos.get('room') or '')[:120]
    if tipo not in ('audio', 'video', 'conferencia') or estado not in ('completada', 'sin_respuesta', 'rechazada'):
        return jsonify({'exito': False, 'error': 'tipo o estado invalido'}), 400

    try:
        peer_id = int(datos.get('peer_id')) if datos.get('peer_id') else None
    except (TypeError, ValueError):
        peer_id = None
    try:
        conversation_id = int(datos.get('conversation_id')) if datos.get('conversation_id') else None
    except (TypeError, ValueError):
        conversation_id = None
    try:
        duracion = max(0, int(datos.get('duracion') or 0))
    except (TypeError, ValueError):
        duracion = 0

    db_session = g.get('db_session_chat')
    if not db_session:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session

    db_session.execute(_text("""
        INSERT INTO chat_llamadas (room, tipo, caller_id, callee_id, conversation_id, estado, duracion_segundos)
        VALUES (:room, :tipo, :caller, :callee, :conv, :estado, :dur)
    """), {'room': room, 'tipo': tipo, 'caller': usuario_id, 'callee': peer_id,
           'conv': conversation_id, 'estado': estado, 'dur': duracion})
    db_session.commit()

    # Llamada perdida -> aviso en el CHAT (no en la campanita). Se empuja al room
    # del destinatario para que el badge del chat se actualice en vivo (toast opcional).
    if estado in ('sin_respuesta', 'rechazada') and peer_id and tipo != 'conferencia':
        try:
            nombre = session.get('usuario_nombre') or 'Un compañero'
            etiqueta = 'videollamada' if tipo == 'video' else 'llamada'
            from interfaces.websocket import manejador_websocket as _ws
            if _ws.socketio:
                _ws.socketio.emit('chat_llamada_perdida', {
                    'de_nombre': nombre,
                    'etiqueta': etiqueta,
                    'conversation_id': conversation_id
                }, room=f'user_{peer_id}')
        except Exception:
            pass  # nunca debe romper el registro

    return jsonify({'exito': True}), 200


@bp_chat.route('/llamadas/historial', methods=['GET'])
@requiere_autenticacion
def historial_llamadas():
    """
    Historial de llamadas del usuario (entrantes y salientes), mas recientes primero.

    Query: limit (default 50, max 200)
    Cada item: { id, tipo, estado, direccion: saliente|entrante, perdida: bool,
                 duracion_segundos, creado_en, otro: {id, nombre, foto},
                 conversation_id }
    """
    from sqlalchemy import text as _text

    usuario_id = obtener_usuario_id()
    try:
        limite = min(200, max(1, int(request.args.get('limit', 50))))
    except (TypeError, ValueError):
        limite = 50

    db_session = g.get('db_session_chat')
    if not db_session:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session

    filas = db_session.execute(_text("""
        SELECT l.id, l.tipo, l.estado, l.caller_id, l.callee_id, l.conversation_id,
               l.duracion_segundos, l.creado_en,
               u.id AS otro_id, u.full_name, u.username,
               u.profile_picture, t.foto_perfil
        FROM chat_llamadas l
        LEFT JOIN usuarios u
               ON u.id = CASE WHEN l.caller_id = :uid THEN l.callee_id ELSE l.caller_id END
        LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE l.caller_id = :uid OR l.callee_id = :uid
        ORDER BY l.creado_en DESC
        LIMIT :lim
    """), {'uid': usuario_id, 'lim': limite}).fetchall()

    llamadas = []
    for f in filas:
        es_saliente = f[3] == usuario_id
        otro_nombre = f[9] or f[10] or ('Conferencia' if f[1] == 'conferencia' else 'Usuario')
        llamadas.append({
            'id': f[0],
            'tipo': f[1],
            'estado': f[2],
            'direccion': 'saliente' if es_saliente else 'entrante',
            'perdida': (not es_saliente) and f[2] in ('sin_respuesta', 'rechazada'),
            'conversation_id': f[5],
            'duracion_segundos': f[6] or 0,
            'creado_en': f[7].isoformat() if f[7] else None,
            'otro': {
                'id': f[8],
                'nombre': otro_nombre,
                'foto': obtener_foto_usuario_con_fallback(f[11], f[12]) if f[8] else None
            }
        })

    return jsonify({'exito': True, 'llamadas': llamadas}), 200


# =============================================================================
# GRABACION DE LLAMADAS/CONFERENCIAS (LiveKit Egress en CT 210)
# El egress compone la sala y escribe un MP4 en /var/livekit/grabaciones,
# servido por nginx interno (8081) SOLO a esta VM. FARO lo entrega con auth.
# Tabla: chat_grabaciones. Doc: livekit-servidor-llamadas-chat-20260612.md
# =============================================================================

def _egress_twirp(metodo: str, cuerpo: dict):
    """Llama un metodo del servicio Egress de LiveKit. Devuelve (ok, data|error)."""
    import os
    import json as _json
    import time as _time
    import urllib.request

    api_key = os.environ.get('LIVEKIT_API_KEY')
    api_secret = os.environ.get('LIVEKIT_API_SECRET')
    api_url = os.environ.get('LIVEKIT_API_URL', 'http://193.16.0.27:7880')
    if not api_key or not api_secret:
        return False, 'LiveKit no configurado'

    ahora = int(_time.time())
    token = _livekit_jwt(api_key, api_secret, {
        'iss': api_key, 'nbf': ahora - 10, 'exp': ahora + 600,
        'video': {'roomRecord': True},
    })
    req = urllib.request.Request(
        f'{api_url}/twirp/livekit.Egress/{metodo}',
        data=_json.dumps(cuerpo).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return True, _json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            err = _json.loads(e.read()).get('msg', str(e))
        except Exception:
            err = f'HTTP {e.code}'
        return False, err
    except Exception as e:
        return False, str(e)


def _usuario_en_sala(room: str, usuario_id: int) -> bool:
    """True si el usuario puede operar/ver una sala (participante de la llamada 1-1
    o cualquier autenticado en conferencias)."""
    if room.startswith('llamada_'):
        partes = room.split('_')[1:]
        return str(usuario_id) in partes
    return room.startswith('conf_')  # conferencias: cualquier participante autenticado


@bp_chat.route('/grabacion/iniciar', methods=['POST'])
@requiere_autenticacion
def iniciar_grabacion():
    """Inicia la grabacion de una sala. Body: { room }."""
    import re as _re
    import time as _time
    from sqlalchemy import text as _text

    usuario_id = obtener_usuario_id()
    datos = request.get_json(silent=True) or {}
    room = (datos.get('room') or '').strip()

    if not room or not _re.match(r'^[a-zA-Z0-9_\-]+$', room) or len(room) > 100:
        return jsonify({'exito': False, 'error': 'Sala invalida'}), 400
    if not _usuario_en_sala(room, usuario_id):
        return jsonify({'exito': False, 'error': 'No autorizado'}), 403

    archivo = f'{room}_{int(_time.time())}.mp4'
    ok, data = _egress_twirp('StartRoomCompositeEgress', {
        'room_name': room,
        'layout': 'grid',
        'file_outputs': [{'file_type': 'MP4', 'filepath': f'/out/{archivo}'}],
    })
    if not ok:
        return jsonify({'exito': False, 'error': f'No se pudo iniciar la grabacion: {data}'}), 502

    egress_id = data.get('egress_id')
    conversation_id = None
    if room.startswith('llamada_'):
        try:
            otro = [int(x) for x in room.split('_')[1:]]
        except ValueError:
            otro = []
        # conv no determinable aqui; queda null (se asocia por el room)

    db_session = g.get('db_session_chat')
    if not db_session:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session
    db_session.execute(_text("""
        INSERT INTO chat_grabaciones (room, egress_id, archivo, solicitante_id, estado)
        VALUES (:room, :eid, :arch, :uid, 'grabando')
    """), {'room': room, 'eid': egress_id, 'arch': archivo, 'uid': usuario_id})
    db_session.commit()

    return jsonify({'exito': True, 'egress_id': egress_id, 'archivo': archivo}), 200


@bp_chat.route('/grabacion/detener', methods=['POST'])
@requiere_autenticacion
def detener_grabacion():
    """Detiene la grabacion. Body: { egress_id }."""
    from sqlalchemy import text as _text

    usuario_id = obtener_usuario_id()
    datos = request.get_json(silent=True) or {}
    egress_id = (datos.get('egress_id') or '').strip()
    if not egress_id:
        return jsonify({'exito': False, 'error': 'egress_id requerido'}), 400

    ok, data = _egress_twirp('StopEgress', {'egress_id': egress_id})
    # Aunque el stop falle (ya terminado), marcamos completada
    db_session = g.get('db_session_chat')
    if not db_session:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session
    db_session.execute(_text("""
        UPDATE chat_grabaciones SET estado = 'completada'
        WHERE egress_id = :eid
    """), {'eid': egress_id})
    db_session.commit()

    return jsonify({'exito': True}), 200


@bp_chat.route('/grabacion/listar', methods=['GET'])
@requiere_autenticacion
def listar_grabaciones():
    """Grabaciones que el usuario solicito o de sus llamadas 1-1, recientes primero."""
    from sqlalchemy import text as _text

    usuario_id = obtener_usuario_id()
    db_session = g.get('db_session_chat')
    if not db_session:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session

    filas = db_session.execute(_text("""
        SELECT id, room, archivo, estado, creado_en, solicitante_id
        FROM chat_grabaciones
        WHERE solicitante_id = :uid
           OR room LIKE 'llamada_%' AND ('_' || :uid || '_') LIKE ('%_' || :uid || '_%')
        ORDER BY creado_en DESC
        LIMIT 100
    """), {'uid': usuario_id}).fetchall()

    grabaciones = []
    for f in filas:
        room = f[1]
        # filtro fino para llamadas 1-1: el usuario debe ser uno de los dos
        if room.startswith('llamada_') and str(usuario_id) not in room.split('_')[1:] and f[5] != usuario_id:
            continue
        grabaciones.append({
            'id': f[0],
            'room': room,
            'archivo': f[2],
            'estado': f[3],
            'creado_en': f[4].isoformat() if f[4] else None,
            'es_conferencia': room.startswith('conf_'),
        })
    return jsonify({'exito': True, 'grabaciones': grabaciones}), 200


@bp_chat.route('/grabacion/descargar/<int:grab_id>', methods=['GET'])
@requiere_autenticacion
def descargar_grabacion(grab_id: int):
    """Entrega el MP4 (stream desde el nginx interno del CT 210, con auth FARO)."""
    import os
    import urllib.request
    from flask import Response, stream_with_context
    from sqlalchemy import text as _text

    usuario_id = obtener_usuario_id()
    db_session = g.get('db_session_chat')
    if not db_session:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session

    fila = db_session.execute(_text("""
        SELECT room, archivo, solicitante_id FROM chat_grabaciones WHERE id = :id
    """), {'id': grab_id}).fetchone()
    if not fila:
        return jsonify({'exito': False, 'error': 'No encontrada'}), 404

    room, archivo, solicitante_id = fila[0], fila[1], fila[2]
    if solicitante_id != usuario_id and not _usuario_en_sala(room, usuario_id):
        return jsonify({'exito': False, 'error': 'No autorizado'}), 403

    base = os.environ.get('LIVEKIT_GRABACIONES_URL', 'http://193.16.0.27:8081')
    try:
        upstream = urllib.request.urlopen(f'{base}/{archivo}', timeout=20)
    except Exception:
        return jsonify({'exito': False, 'error': 'La grabacion aun no esta disponible'}), 404

    def generar():
        while True:
            trozo = upstream.read(65536)
            if not trozo:
                break
            yield trozo

    return Response(stream_with_context(generar()), mimetype='video/mp4', headers={
        'Content-Disposition': f'attachment; filename="{archivo}"'
    })


# =============================================================================
# ACCIONES DE CONVERSACION (archivar / vaciar / eliminar) — SOFT, sin perder datos
# El historial completo queda en BD y es visible desde el panel admin del chat.
# =============================================================================

def _es_master(usuario_id):
    try:
        from sqlalchemy import text as _t
        ses = g.get("db_session_chat")
        if not ses:
            ses = obtener_gestor().session(); g.db_session_chat = ses
        r = ses.execute(_t("SELECT role FROM usuarios WHERE id = :id"), {"id": usuario_id}).fetchone()
        return bool(r and str(r[0]) in ("master", "master_admin"))
    except Exception:
        return False


@bp_chat.route("/conversations/<int:conversacion_id>/archivar", methods=["POST"])
@requiere_autenticacion
def archivar_conversacion(conversacion_id):
    """Archiva/desarchiva la conversacion SOLO para el usuario actual (reversible)."""
    from sqlalchemy import text as _t
    usuario_id = obtener_usuario_id()
    datos = request.get_json(silent=True) or {}
    archivar = datos.get("archivar", True)
    ses = g.get("db_session_chat")
    if not ses:
        ses = obtener_gestor().session(); g.db_session_chat = ses
    ses.execute(_t(
        "UPDATE chat_participants SET is_archived = :a, archived_at = CASE WHEN :a THEN NOW() ELSE NULL END "
        "WHERE conversation_id = :c AND user_id = :u"
    ), {"a": bool(archivar), "c": conversacion_id, "u": usuario_id})
    ses.commit()
    return jsonify({"exito": True, "success": True, "archivada": bool(archivar)}), 200


@bp_chat.route("/conversations/<int:conversacion_id>/vaciar", methods=["POST"])
@requiere_autenticacion
def vaciar_conversacion(conversacion_id):
    """Vacia la conversacion para el usuario (los mensajes previos dejan de mostrarse,
    pero NO se borran de la BD; quedan en el historial admin)."""
    from sqlalchemy import text as _t
    usuario_id = obtener_usuario_id()
    ses = g.get("db_session_chat")
    if not ses:
        ses = obtener_gestor().session(); g.db_session_chat = ses
    ses.execute(_t(
        "UPDATE chat_participants SET cleared_at = NOW() WHERE conversation_id = :c AND user_id = :u"
    ), {"c": conversacion_id, "u": usuario_id})
    ses.commit()
    return jsonify({"exito": True, "success": True}), 200


@bp_chat.route("/conversations/<int:conversacion_id>/eliminar", methods=["POST"])
@requiere_autenticacion
def eliminar_conversacion(conversacion_id):
    """Elimina la conversacion de la lista del usuario (borrado LOGICO: is_active=false).
    Los datos siguen en BD y son recuperables desde el panel admin."""
    from sqlalchemy import text as _t
    usuario_id = obtener_usuario_id()
    ses = g.get("db_session_chat")
    if not ses:
        ses = obtener_gestor().session(); g.db_session_chat = ses
    ses.execute(_t(
        "UPDATE chat_participants SET is_active = FALSE, left_at = NOW() "
        "WHERE conversation_id = :c AND user_id = :u"
    ), {"c": conversacion_id, "u": usuario_id})
    ses.commit()
    return jsonify({"exito": True, "success": True}), 200


# ---------- PANEL ADMIN: historial de conversaciones (recuperar/revisar) ----------

@bp_chat.route("/admin/conversaciones", methods=["GET"])
@requiere_autenticacion
def admin_listar_conversaciones():
    """Lista TODAS las conversaciones (incluidas archivadas/eliminadas) para master.
    Permite revisar/recuperar. Query: q (filtro por participante)."""
    from sqlalchemy import text as _t
    usuario_id = obtener_usuario_id()
    if not _es_master(usuario_id):
        return jsonify({"exito": False, "error": "Solo administradores"}), 403
    q = (request.args.get("q") or "").strip()
    ses = g.get("db_session_chat")
    if not ses:
        ses = obtener_gestor().session(); g.db_session_chat = ses
    base = (
        "SELECT c.id, c.conversation_type, c.name, c.created_at, "
        "  (SELECT count(*) FROM chat_messages m WHERE m.conversation_id = c.id) AS n_msgs, "
        "  (SELECT max(m.created_at) FROM chat_messages m WHERE m.conversation_id = c.id) AS ultimo, "
        "  (SELECT string_agg(DISTINCT u.full_name, \' , \') FROM chat_participants p "
        "      JOIN usuarios u ON u.id = p.user_id WHERE p.conversation_id = c.id) AS participantes "
        "FROM chat_conversations c "
    )
    params = {}
    if q:
        base += ("WHERE c.id IN (SELECT p.conversation_id FROM chat_participants p "
                 "JOIN usuarios u ON u.id = p.user_id WHERE u.full_name ILIKE :q) ")
        params["q"] = "%" + q + "%"
    base += "ORDER BY ultimo DESC NULLS LAST LIMIT 200"
    filas = ses.execute(_t(base), params).fetchall()
    convs = [{
        "id": f[0], "tipo": f[1], "nombre": f[2],
        "creado_en": f[3].isoformat() if f[3] else None,
        "n_mensajes": f[4] or 0,
        "ultimo": f[5].isoformat() if f[5] else None,
        "participantes": f[6] or "",
    } for f in filas]
    return jsonify({"exito": True, "conversaciones": convs}), 200


@bp_chat.route("/admin/conversaciones/<int:conversacion_id>/mensajes", methods=["GET"])
@requiere_autenticacion
def admin_mensajes_conversacion(conversacion_id):
    """Todos los mensajes de una conversacion (para revision/recuperacion) — master."""
    from sqlalchemy import text as _t
    usuario_id = obtener_usuario_id()
    if not _es_master(usuario_id):
        return jsonify({"exito": False, "error": "Solo administradores"}), 403
    ses = g.get("db_session_chat")
    if not ses:
        ses = obtener_gestor().session(); g.db_session_chat = ses
    filas = ses.execute(_t(
        "SELECT m.id, m.sender_id, u.full_name, m.content, m.message_type, m.created_at, m.is_deleted "
        "FROM chat_messages m LEFT JOIN usuarios u ON u.id = m.sender_id "
        "WHERE m.conversation_id = :c ORDER BY m.created_at ASC LIMIT 2000"
    ), {"c": conversacion_id}).fetchall()
    msgs = [{
        "id": f[0], "remitente_id": f[1], "remitente": f[2] or "Sistema",
        "contenido": f[3], "tipo": f[4],
        "fecha": f[5].isoformat() if f[5] else None,
        "eliminado": bool(f[6]),
    } for f in filas]
    return jsonify({"exito": True, "mensajes": msgs}), 200


# =============================================================================
# BUSQUEDA DE MENSAJES (dentro de una conversacion o en TODAS) — rapida por SQL
# =============================================================================

@bp_chat.route("/buscar-mensajes", methods=["GET"])
@requiere_autenticacion
def buscar_mensajes():
    """Busca mensajes por contenido. Query: q (texto), conversation_id (opcional).
    Sin conversation_id busca en TODAS las conversaciones del usuario."""
    from sqlalchemy import text as _t
    usuario_id = obtener_usuario_id()
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"exito": True, "resultados": []}), 200
    try:
        conv_id = int(request.args.get("conversation_id")) if request.args.get("conversation_id") else None
    except (TypeError, ValueError):
        conv_id = None

    ses = g.get("db_session_chat")
    if not ses:
        ses = obtener_gestor().session(); g.db_session_chat = ses

    sql = (
        "SELECT m.id, m.conversation_id, m.content, m.created_at, m.message_type, "
        "  u.full_name AS remitente, c.conversation_type, c.name AS conv_name, "
        "  p.cleared_at "
        "FROM chat_messages m "
        "JOIN chat_participants p ON p.conversation_id = m.conversation_id AND p.user_id = :uid AND p.is_active = TRUE "
        "JOIN chat_conversations c ON c.id = m.conversation_id "
        "LEFT JOIN usuarios u ON u.id = m.sender_id "
        "WHERE m.is_deleted = FALSE AND m.content ILIKE :q "
    )
    params = {"uid": usuario_id, "q": "%" + q + "%"}
    if conv_id:
        sql += "AND m.conversation_id = :cid "
        params["cid"] = conv_id
    sql += "ORDER BY m.created_at DESC LIMIT 60"

    filas = ses.execute(_t(sql), params).fetchall()
    # Para chats directos, mostrar el nombre del OTRO participante como titulo
    res = []
    for f in filas:
        cleared = f[8]
        creado = f[3]
        if cleared and creado and creado <= cleared:
            continue  # respeta "vaciar"
        titulo = f[7]
        if (f[6] or "") == "direct":
            otro = ses.execute(_t(
                "SELECT u.full_name FROM chat_participants p JOIN usuarios u ON u.id = p.user_id "
                "WHERE p.conversation_id = :c AND p.user_id <> :u LIMIT 1"
            ), {"c": f[1], "u": usuario_id}).fetchone()
            if otro and otro[0]:
                titulo = otro[0]
        res.append({
            "id": f[0],
            "conversation_id": f[1],
            "contenido": f[2],
            "fecha": creado.isoformat() if creado else None,
            "tipo": f[4],
            "remitente": f[5] or "Sistema",
            "conversation_type": f[6],
            "titulo": titulo or "Conversación",
        })
    return jsonify({"exito": True, "resultados": res, "total": len(res)}), 200
