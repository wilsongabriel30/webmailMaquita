# -*- coding: utf-8 -*-
"""
Modelo SQLAlchemy: Usuario - Módulo Usuarios

Modelo de persistencia para la tabla de usuarios.
Mapea a la tabla 'usuarios' existente en la base de datos.

CAPA: infraestructura/persistencia/modelos
REGLAS:
- Puede usar SQLAlchemy
- Mapea entre BD y entidades de dominio

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado a arquitectura modular: 2026-01-04
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from infraestructura.base_datos.base import Base


class ModeloUsuario(Base):
    """
    Modelo SQLAlchemy para la tabla usuarios.

    Mapea a la tabla 'usuarios' existente en la base de datos
    de nomina (193.16.0.132:5432/nomina).

    Esquema: public.usuarios
    """

    __tablename__ = 'usuarios'
    __table_args__ = {'schema': 'public', 'extend_existing': True}

    # Columnas principales
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200))

    # Estado y rol
    role = Column(String(50), default='user')
    active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    force_password_change = Column(Boolean, default=False)

    # Foto de perfil
    profile_picture = Column(String(500), nullable=True)

    # Seguridad
    login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    # Timestamps
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, onupdate=datetime.now)
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)

    # Relacion con trabajador (sin ForeignKey para evitar dependencia)
    trabajador_id = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<ModeloUsuario(id={self.id}, username='{self.username}')>"

    def to_dict(self):
        """Convierte el modelo a diccionario (para debugging)."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'active': self.active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
