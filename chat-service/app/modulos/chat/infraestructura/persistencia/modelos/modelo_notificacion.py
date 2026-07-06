# -*- coding: utf-8 -*-
"""
Modelo SQLAlchemy: Notificaciones - Modulo Chat

Modelo de persistencia para las notificaciones del sistema.

CAPA: infraestructura/persistencia/modelos

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado a modulos: 2026-01-05
"""

from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, Integer, String, DateTime, Boolean, Text, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from compartido.infraestructura.base_datos import Base


class ModeloNotificacion(Base):
    """
    Modelo SQLAlchemy para la tabla notifications.

    Representa una notificacion del sistema para un usuario.
    """

    __tablename__ = 'notifications'
    __table_args__ = {'schema': 'public', 'extend_existing': True}

    # Columnas principales
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('public.usuarios.id'), nullable=False, index=True)

    # Tipo de notificacion
    type = Column(String(50), nullable=False, index=True)  # chat, social, system, etc.

    # Contenido
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)

    # Referencia al objeto relacionado
    reference_type = Column(String(50), nullable=True)  # message, post, comment, etc.
    reference_id = Column(BigInteger, nullable=True)

    # URL para navegacion
    action_url = Column(String(500), nullable=True)

    # Datos adicionales
    data = Column(JSONB, default={})

    # Estado
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.now, index=True)

    def __repr__(self):
        return f"<ModeloNotificacion(id={self.id}, user_id={self.user_id}, type='{self.type}')>"

    def to_dict(self):
        """Convierte el modelo a diccionario."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'reference_type': self.reference_type,
            'reference_id': self.reference_id,
            'action_url': self.action_url,
            'data': self.data or {},
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
