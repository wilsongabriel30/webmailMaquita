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

