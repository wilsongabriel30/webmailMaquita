# -*- coding: utf-8 -*-
"""Conversaciones: listar, detalle, directa, crear grupo.
Extraído de controlador_chat.py (líneas 156-541) el 28/08/2026 sin cambios en las rutas. Las rutas se registran en
bp_chat al importar este módulo (lo hace controlador_chat.py, que sigue siendo el punto de entrada)."""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, servicio, autenticación…)

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
                    # T-48: ademas del online/offline de siempre, el estado que hay que
                    # pintar (conectado / ausente / ocupado), calculado con la regla comun.
                    try:
                        from interfaces.websocket import estado_presencia as _ep
                        user_presencia = dict(user_presencia)
                        user_presencia['estado'] = _ep.estado_de(u_id)
                    except Exception:
                        pass

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
                        # T-48: el estado que hay que pintar en el puntito
                        'estado': user_presencia.get('estado', 'ausente'),
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
                # Grupos: foto del grupo (avatar_path) para el frontend
                if conv_dict.get('tipo') == 'group' and conv_dict.get('avatar_ruta'):
                    conv_dict['avatar'] = conv_dict['avatar_ruta']

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
                                'last_seen': otro_usuario.get('last_seen'),
                                # T-48: viaja hasta el frontend para pintar el puntito
                                'estado': otro_usuario.get('estado', 'ausente')
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

