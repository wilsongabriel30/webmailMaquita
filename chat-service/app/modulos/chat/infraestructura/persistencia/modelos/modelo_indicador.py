# -*- coding: utf-8 -*-
"""
Modelo SQLAlchemy: Indicador de Escritura - Modulo Chat

Modelo de persistencia para los indicadores de accion del chat.
Mapea a la tabla 'chat_typing_indicators'.

CAPA: infraestructura/persistencia/modelos

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado a modulos: 2026-01-05
"""

from datetime import datetime
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey
from compartido.infraestructura.base_datos import Base


class ModeloIndicadorAccion(Base):
    """
    Modelo SQLAlchemy para la tabla chat_typing_indicators.

    Representa un indicador de accion (escribiendo, grabando, etc.)
    """

    __tablename__ = 'chat_typing_indicators'
    __table_args__ = {'schema': 'public', 'extend_existing': True}

    # Clave compuesta
    conversation_id = Column(
        BigInteger,
        ForeignKey('public.chat_conversations.id'),
        primary_key=True
    )
    user_id = Column(
        Integer,
        ForeignKey('public.usuarios.id'),
        primary_key=True
    )

    # Tiempo de inicio
    started_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    def __repr__(self):
        return f"<ModeloIndicadorAccion(conv={self.conversation_id}, user={self.user_id})>"
