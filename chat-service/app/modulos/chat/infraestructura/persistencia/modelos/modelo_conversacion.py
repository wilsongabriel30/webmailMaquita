# -*- coding: utf-8 -*-
"""
Modelo SQLAlchemy: Conversacion - Modulo Chat

Modelo de persistencia para las tablas de conversaciones del chat.
Mapea a las tablas 'chat_conversations' y 'chat_participants'.

CAPA: infraestructura/persistencia/modelos
REGLAS:
- Puede usar SQLAlchemy
- Mapea entre BD y entidades de dominio

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado a modulos: 2026-01-05
"""

from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, Integer, String, DateTime, Boolean, Text, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from compartido.infraestructura.base_datos import Base


class ModeloConversacion(Base):
    """
    Modelo SQLAlchemy para la tabla chat_conversations.

    Representa una conversacion de chat (directa o grupal).
    """

    __tablename__ = 'chat_conversations'
    __table_args__ = {'schema': 'public', 'extend_existing': True}

    # Columnas principales (BigInteger para coincidir con bigint)
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    public_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    conversation_type = Column(String(20), nullable=False, default='direct')  # direct, group
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    avatar_path = Column(String(500), nullable=True)

    # Creador (para grupos)
    created_by = Column(Integer, ForeignKey('public.usuarios.id'), nullable=True)

    # Ultimo mensaje (para ordenamiento y preview)
    last_message_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_message_preview = Column(Text, nullable=True)

    # Estado
    is_active = Column(Boolean, default=True)

    # Configuracion JSONB
    settings = Column(JSONB, default={})

    # Invitaciones
    invite_link_enabled = Column(Boolean, default=True)
    disappearing_messages_duration = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    # Relaciones
    participants = relationship(
        'ModeloParticipante',
        back_populates='conversation',
        lazy='dynamic'
    )
    messages = relationship(
        'ModeloMensaje',
        back_populates='conversation',
        lazy='dynamic'
    )

    def __repr__(self):
        return f"<ModeloConversacion(id={self.id}, type='{self.conversation_type}', name='{self.name}')>"


class ModeloParticipante(Base):
    """
    Modelo SQLAlchemy para la tabla chat_participants.

    Representa un participante en una conversacion.
    """

    __tablename__ = 'chat_participants'
    __table_args__ = {'schema': 'public', 'extend_existing': True}

    # Columnas principales
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(
        BigInteger,
        ForeignKey('public.chat_conversations.id'),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey('public.usuarios.id'),
        nullable=False,
        index=True
    )

    # Rol en la conversacion
    role = Column(String(20), default='member')  # admin, moderator, member

    # Personalizacion
    nickname = Column(String(100), nullable=True)

    # Silenciar notificaciones
    is_muted = Column(Boolean, default=False)
    muted_until = Column(DateTime(timezone=True), nullable=True)

    # Estado de participacion
    is_active = Column(Boolean, default=True)

    # Lectura de mensajes
    last_read_message_id = Column(BigInteger, nullable=True)
    last_read_at = Column(DateTime(timezone=True), nullable=True)
    unread_count = Column(Integer, default=0)

    # Archivo
    is_archived = Column(Boolean, default=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    joined_at = Column(DateTime(timezone=True), default=datetime.now)
    left_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    conversation = relationship(
        'ModeloConversacion',
        back_populates='participants'
    )

    def __repr__(self):
        return f"<ModeloParticipante(id={self.id}, user_id={self.user_id}, role='{self.role}')>"
