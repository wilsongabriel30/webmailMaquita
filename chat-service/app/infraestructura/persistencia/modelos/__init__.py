# -*- coding: utf-8 -*-
"""
Modelos SQLAlchemy - BRIDGE LEGACY

NOTA: Este modulo es un bridge de compatibilidad.
Los modelos reales estan en:
- modulos/usuarios/infraestructura/persistencia/modelos/
- modulos/chat/infraestructura/persistencia/modelos/

Para nuevo codigo, usar:
    from modulos.usuarios.infraestructura.persistencia.modelos import ModeloUsuario
    from modulos.chat.infraestructura.persistencia.modelos import ModeloConversacion

Autor: Wilson Arguello
Migrado: 2026-01-05
"""

# Modelo de usuario (desde modulos/usuarios via puente local)
from infraestructura.persistencia.modelos.modelo_usuario import ModeloUsuario

# Modelos de chat - Conversaciones
from infraestructura.persistencia.modelos.modelo_conversacion import (
    ModeloConversacion,
    ModeloParticipante
)

# Modelos de chat - Mensajes
from infraestructura.persistencia.modelos.modelo_mensaje import (
    ModeloMensaje,
    ModeloMediaMensaje,
    ModeloEstadoMensaje
)

# Modelos de chat - Reacciones
from infraestructura.persistencia.modelos.modelo_reaccion import ModeloReaccion

# Modelos de chat - Presencia y Bloqueos
from infraestructura.persistencia.modelos.modelo_presencia import (
    ModeloPresencia,
    ModeloBloqueo
)

# Modelo de notificaciones
from infraestructura.persistencia.modelos.modelo_notificacion import ModeloNotificacion

__all__ = [
    # Usuario
    'ModeloUsuario',
    # Chat - Conversaciones
    'ModeloConversacion',
    'ModeloParticipante',
    # Chat - Mensajes
    'ModeloMensaje',
    'ModeloMediaMensaje',
    'ModeloEstadoMensaje',
    # Chat - Reacciones
    'ModeloReaccion',
    # Chat - Presencia y Bloqueos
    'ModeloPresencia',
    'ModeloBloqueo',
    # Notificaciones
    'ModeloNotificacion',
]
