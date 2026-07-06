# -*- coding: utf-8 -*-
"""
Modelo SQLAlchemy: Presencia y Bloqueos - Modulo Chat

Modelos de persistencia para presencia de usuarios y bloqueos.
Mapea a las tablas 'chat_user_presence' y 'chat_blocked_users'.

CAPA: infraestructura/persistencia/modelos

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado a modulos: 2026-01-05
"""

from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, Integer, String, DateTime, Boolean, Text, ForeignKey, UniqueConstraint
)
from compartido.infraestructura.base_datos import Base


class ModeloPresencia(Base):
    """
    Modelo SQLAlchemy para la tabla chat_user_presence.

    Representa el estado de presencia de un usuario.
    """

    __tablename__ = 'chat_user_presence'
    __table_args__ = {'schema': 'public', 'extend_existing': True}

    # Columnas principales (user_id es la primary key en esta tabla)
    user_id = Column(
        Integer,
        ForeignKey('public.usuarios.id'),
        primary_key=True,
        index=True
    )

    # Estado de presencia
    is_online = Column(Boolean, default=False)
    last_seen_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<ModeloPresencia(user_id={self.user_id}, is_online={self.is_online})>"


class ModeloBloqueo(Base):
    """
    Modelo SQLAlchemy para la tabla chat_blocked_users.

    Representa un bloqueo entre usuarios.
    """

    __tablename__ = 'chat_blocked_users'
    __table_args__ = (
        UniqueConstraint('blocker_id', 'blocked_id', name='uq_block_users'),
        {'schema': 'public', 'extend_existing': True}
    )

    # Columnas principales
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    blocker_id = Column(
        Integer,
        ForeignKey('public.usuarios.id'),
        nullable=False,
        index=True
    )
    blocked_id = Column(
        Integer,
        ForeignKey('public.usuarios.id'),
        nullable=False,
        index=True
    )

    # Razon del bloqueo (opcional)
    reason = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.now)

    def __repr__(self):
        return f"<ModeloBloqueo(blocker_id={self.blocker_id}, blocked_id={self.blocked_id})>"
