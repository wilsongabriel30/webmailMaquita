# -*- coding: utf-8 -*-
"""
Modelo SQLAlchemy: Mensaje - Modulo Chat

Modelo de persistencia para las tablas de mensajes del chat.
Mapea a las tablas 'chat_messages', 'chat_message_media' y 'chat_message_status'.

CAPA: infraestructura/persistencia/modelos
REGLAS:
- Puede usar SQLAlchemy
- Mapea entre BD y entidades de dominio

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado a modulos: 2026-01-05
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, BigInteger, Integer, String, DateTime, Boolean, Text, ForeignKey, SmallInteger, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from compartido.infraestructura.base_datos import Base


def utc_now():
    """Retorna datetime actual en UTC."""
    return datetime.now(timezone.utc)


class ModeloMensaje(Base):
    """
    Modelo SQLAlchemy para la tabla chat_messages.

    Representa un mensaje en una conversacion.
    """

    __tablename__ = 'chat_messages'
    __table_args__ = {'schema': 'public', 'extend_existing': True}

    # Columnas principales
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    public_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)

    # Client ID para idempotencia - evita duplicados en reintentos
    client_id = Column(String(64), unique=True, nullable=True, index=True)

    conversation_id = Column(
        BigInteger,
        ForeignKey('public.chat_conversations.id'),
        nullable=False,
        index=True
    )
    sender_id = Column(
        Integer,
        ForeignKey('public.usuarios.id'),
        nullable=False,
        index=True
    )

    # Contenido
    content = Column(Text, nullable=True)
    message_type = Column(String(20), default='text')  # text, image, video, audio, document, system, reply

    # Respuesta a otro mensaje
    reply_to_id = Column(
        BigInteger,
        ForeignKey('public.chat_messages.id'),
        nullable=True
    )

    # Mensaje reenviado
    forwarded_from_id = Column(
        BigInteger,
        ForeignKey('public.chat_messages.id'),
        nullable=True
    )

    # Estado de edicion
    is_edited = Column(Boolean, default=False)

    # Estado de eliminacion
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_for_everyone = Column(Boolean, default=False)

    # Mensajes fijados (Feature 3)
    is_pinned = Column(Boolean, default=False, server_default='false')
    pinned_at = Column(DateTime(timezone=True), nullable=True)
    pinned_by = Column(BigInteger, ForeignKey('public.usuarios.id'), nullable=True)

    # Metadata adicional (JSONB)
    msg_metadata = Column('metadata', JSONB, default={})

    # Menciones (array de IDs de usuarios)
    mentions = Column(ARRAY(Integer), default=[])

    # Timestamps - usar UTC para consistencia
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=func.now())

    # Relaciones
    conversation = relationship(
        'ModeloConversacion',
        back_populates='messages'
    )
    media = relationship(
        'ModeloMediaMensaje',
        back_populates='message',
        lazy='joined'
    )
    reactions = relationship(
        'ModeloReaccion',
        back_populates='message',
        lazy='select'
    )
    reply_to = relationship(
        'ModeloMensaje',
        remote_side=[id],
        foreign_keys=[reply_to_id]
    )

    def __repr__(self):
        return f"<ModeloMensaje(id={self.id}, type='{self.message_type}', sender_id={self.sender_id})>"


class ModeloMediaMensaje(Base):
    """
    Modelo SQLAlchemy para la tabla chat_message_media.

    Representa un archivo multimedia adjunto a un mensaje.
    """

    __tablename__ = 'chat_message_media'
    __table_args__ = {'schema': 'public', 'extend_existing': True}

    # Columnas principales
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(
        BigInteger,
        ForeignKey('public.chat_messages.id'),
        nullable=False,
        index=True
    )

    # Tipo de archivo
    media_type = Column(String(20), nullable=False)  # image, video, audio, document, sticker

    # Informacion del archivo
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=False, default=0)
    mime_type = Column(String(100), nullable=True)

    # Dimensiones (para imagenes/videos)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # Duracion (para audio/video)
    duration = Column(Integer, nullable=True)  # segundos

    # Miniatura
    thumbnail_path = Column(String(500), nullable=True)

    # Orden (para mensajes con multiples archivos)
    display_order = Column(SmallInteger, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now())

    # Relaciones
    message = relationship(
        'ModeloMensaje',
        back_populates='media'
    )

    def __repr__(self):
        return f"<ModeloMediaMensaje(id={self.id}, type='{self.media_type}', name='{self.file_name}')>"


class ModeloEstadoMensaje(Base):
    """
    Modelo SQLAlchemy para la tabla chat_message_status.

    Representa el estado de entrega/lectura de un mensaje para un usuario.
    """

    __tablename__ = 'chat_message_status'
    __table_args__ = {'schema': 'public', 'extend_existing': True}

    # Columnas principales
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(
        BigInteger,
        ForeignKey('public.chat_messages.id'),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey('public.usuarios.id'),
        nullable=False,
        index=True
    )

    # Estado de entrega
    is_delivered = Column(Boolean, default=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    # Estado de lectura
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<ModeloEstadoMensaje(message_id={self.message_id}, user_id={self.user_id})>"
