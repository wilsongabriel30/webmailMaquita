# -*- coding: utf-8 -*-
"""
Modelo SQLAlchemy: Reaccion - Modulo Chat

Modelo de persistencia para la tabla de reacciones del chat.
Mapea a la tabla 'chat_message_reactions'.

CAPA: infraestructura/persistencia/modelos

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado a modulos: 2026-01-05
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from compartido.infraestructura.base_datos import Base


class ModeloReaccion(Base):
    """
    Modelo SQLAlchemy para la tabla chat_message_reactions.

    Representa una reaccion emoji a un mensaje.
    """

    __tablename__ = 'chat_message_reactions'
    __table_args__ = (
        UniqueConstraint('message_id', 'user_id', name='uq_reaction_message_user'),
        {'schema': 'public', 'extend_existing': True}
    )

    # Columnas principales
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(
        Integer,
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

    # Emoji de la reaccion
    emoji = Column(String(10), nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.now)

    # Relaciones
    message = relationship(
        'ModeloMensaje',
        back_populates='reactions'
    )

    def __repr__(self):
        return f"<ModeloReaccion(message_id={self.message_id}, user_id={self.user_id}, emoji='{self.emoji}')>"
