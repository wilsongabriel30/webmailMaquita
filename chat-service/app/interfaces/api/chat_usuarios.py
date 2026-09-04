# -*- coding: utf-8 -*-
"""Búsqueda de usuarios, trabajadores activos, no leídos.
Extraído de controlador_chat.py (líneas 2184-2438) el 28/08/2026 sin cambios en las rutas. Las rutas se registran en
bp_chat al importar este módulo (lo hace controlador_chat.py, que sigue siendo el punto de entrada)."""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, servicio, autenticación…)

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


@bp_chat.route('/no-leidos', methods=['GET'])
@requiere_autenticacion
def obtener_no_leidos_app():
    """T-42: total de mensajes sin leer para el globito del cliente Windows.

    Response: {"total": N}. Ante cualquier error responde 0: un contador nunca
    debe romper la app.
    """
    try:
        servicio = obtener_servicio_chat()
        conversaciones = servicio.obtener_conversaciones(obtener_usuario_id(), limite=100)
        return jsonify({'total': sum(c.mensajes_no_leidos for c in conversaciones)}), 200
    except Exception:
        import traceback
        traceback.print_exc()
        return jsonify({'total': 0}), 200
