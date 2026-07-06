# -*- coding: utf-8 -*-
"""
Adaptador: Repositorio Usuario PostgreSQL - Módulo Usuarios

Implementa IRepositorioUsuario usando SQLAlchemy y PostgreSQL.
Este es un adaptador de infraestructura.

CAPA: infraestructura/persistencia
REGLAS:
- Implementa interfaces definidas en dominio/repositorios
- Puede usar SQLAlchemy y otras librerías externas
- Traduce entre entidades de dominio y modelos de persistencia

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado a arquitectura modular: 2026-01-04
"""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_

from modulos.usuarios.dominio.repositorios import IRepositorioUsuario
from modulos.usuarios.dominio.entidades import Usuario, RolUsuario, EstadoUsuario
from .modelos import ModeloUsuario


class RepositorioUsuarioPostgreSQL(IRepositorioUsuario):
    """
    Implementación del repositorio de usuarios usando PostgreSQL.

    Traduce entre la entidad de dominio (Usuario) y el modelo
    de persistencia (ModeloUsuario de SQLAlchemy).

    Ejemplo:
        db_session = obtener_session()
        repositorio = RepositorioUsuarioPostgreSQL(db_session)
        usuario = repositorio.obtener_por_id(1)
    """

    def __init__(self, session: Session):
        """
        Inicializa el repositorio.

        Args:
            session: Sesión de SQLAlchemy
        """
        self._session = session

    # ─────────────────────────────────────────────────────────────────
    # Métodos base (IRepositorioBase)
    # ─────────────────────────────────────────────────────────────────

    def obtener_por_id(self, id: int) -> Optional[Usuario]:
        """Obtiene un usuario por su ID."""
        modelo = self._session.query(ModeloUsuario).filter_by(id=id).first()
        return self._a_entidad(modelo) if modelo else None

    def obtener_todos(self) -> List[Usuario]:
        """Obtiene todos los usuarios."""
        modelos = self._session.query(ModeloUsuario).all()
        return [self._a_entidad(m) for m in modelos]

    def guardar(self, entidad: Usuario) -> Usuario:
        """Guarda un usuario (crear o actualizar)."""
        if entidad.id:
            # Actualizar existente
            modelo = self._session.query(ModeloUsuario).filter_by(id=entidad.id).first()
            if modelo:
                self._actualizar_modelo(modelo, entidad)
        else:
            # Crear nuevo
            modelo = self._a_modelo(entidad)
            self._session.add(modelo)

        self._session.commit()

        if not entidad.id:
            entidad.id = modelo.id

        return entidad

    def eliminar(self, id: int) -> bool:
        """Elimina un usuario por su ID."""
        modelo = self._session.query(ModeloUsuario).filter_by(id=id).first()
        if modelo:
            self._session.delete(modelo)
            self._session.commit()
            return True
        return False

    def existe(self, id: int) -> bool:
        """Verifica si existe un usuario con el ID."""
        return self._session.query(ModeloUsuario).filter_by(id=id).count() > 0

    def contar(self) -> int:
        """Cuenta el total de usuarios."""
        return self._session.query(ModeloUsuario).count()

    # ─────────────────────────────────────────────────────────────────
    # Métodos específicos de usuario (IRepositorioUsuario)
    # ─────────────────────────────────────────────────────────────────

    def obtener_por_nombre_usuario(self, nombre_usuario: str) -> Optional[Usuario]:
        """Obtiene un usuario por nombre de usuario."""
        modelo = self._session.query(ModeloUsuario).filter_by(
            username=nombre_usuario
        ).first()
        return self._a_entidad(modelo) if modelo else None

    def obtener_por_correo(self, correo: str) -> Optional[Usuario]:
        """Obtiene un usuario por correo electrónico."""
        modelo = self._session.query(ModeloUsuario).filter_by(
            email=correo.lower()
        ).first()
        return self._a_entidad(modelo) if modelo else None

    def obtener_por_nombre_usuario_o_correo(self, identificador: str) -> Optional[Usuario]:
        """Obtiene un usuario por nombre de usuario o correo."""
        modelo = self._session.query(ModeloUsuario).filter(
            or_(
                ModeloUsuario.username == identificador,
                ModeloUsuario.email == identificador.lower()
            )
        ).first()
        return self._a_entidad(modelo) if modelo else None

    def existe_nombre_usuario(self, nombre_usuario: str) -> bool:
        """Verifica si existe el nombre de usuario."""
        return self._session.query(ModeloUsuario).filter_by(
            username=nombre_usuario
        ).count() > 0

    def existe_correo(self, correo: str) -> bool:
        """Verifica si existe el correo."""
        return self._session.query(ModeloUsuario).filter_by(
            email=correo.lower()
        ).count() > 0

    def obtener_por_rol(self, rol: str) -> List[Usuario]:
        """Obtiene usuarios por rol."""
        modelos = self._session.query(ModeloUsuario).filter_by(role=rol).all()
        return [self._a_entidad(m) for m in modelos]

    def obtener_activos(self) -> List[Usuario]:
        """Obtiene usuarios activos."""
        modelos = self._session.query(ModeloUsuario).filter_by(
            active=True
        ).all()
        return [self._a_entidad(m) for m in modelos]

    def obtener_bloqueados(self) -> List[Usuario]:
        """Obtiene usuarios bloqueados (con locked_until vigente)."""
        modelos = self._session.query(ModeloUsuario).filter(
            ModeloUsuario.locked_until > datetime.now()
        ).all()
        return [self._a_entidad(m) for m in modelos]

    def actualizar_ultimo_acceso(self, id_usuario: int) -> bool:
        """Actualiza la fecha de último acceso."""
        modelo = self._session.query(ModeloUsuario).filter_by(id=id_usuario).first()
        if modelo:
            modelo.last_login = datetime.now()
            self._session.commit()
            return True
        return False

    def incrementar_intentos_fallidos(self, id_usuario: int) -> int:
        """Incrementa el contador de intentos fallidos."""
        modelo = self._session.query(ModeloUsuario).filter_by(id=id_usuario).first()
        if modelo:
            modelo.login_attempts = (modelo.login_attempts or 0) + 1
            self._session.commit()
            return modelo.login_attempts
        return 0

    def reiniciar_intentos_fallidos(self, id_usuario: int) -> bool:
        """Reinicia el contador de intentos fallidos."""
        modelo = self._session.query(ModeloUsuario).filter_by(id=id_usuario).first()
        if modelo:
            modelo.login_attempts = 0
            modelo.locked_until = None
            self._session.commit()
            return True
        return False

    def bloquear_usuario(self, id_usuario: int, duracion_minutos: int) -> bool:
        """Bloquea un usuario temporalmente."""
        modelo = self._session.query(ModeloUsuario).filter_by(id=id_usuario).first()
        if modelo:
            modelo.locked_until = datetime.now() + timedelta(minutes=duracion_minutos)
            self._session.commit()
            return True
        return False

    def desbloquear_usuario(self, id_usuario: int) -> bool:
        """Desbloquea un usuario."""
        modelo = self._session.query(ModeloUsuario).filter_by(id=id_usuario).first()
        if modelo:
            modelo.active = True
            modelo.locked_until = None
            modelo.login_attempts = 0
            self._session.commit()
            return True
        return False

    def cambiar_contrasena(self, id_usuario: int, contrasena_cifrada: str) -> bool:
        """Cambia la contraseña de un usuario."""
        modelo = self._session.query(ModeloUsuario).filter_by(id=id_usuario).first()
        if modelo:
            modelo.password_hash = contrasena_cifrada
            modelo.updated_at = datetime.now()
            self._session.commit()
            return True
        return False

    # ─────────────────────────────────────────────────────────────────
    # Métodos de mapeo
    # ─────────────────────────────────────────────────────────────────

    def _a_entidad(self, modelo: ModeloUsuario) -> Usuario:
        """
        Convierte un modelo de SQLAlchemy a entidad de dominio.

        Args:
            modelo: Modelo de persistencia

        Returns:
            Entidad de dominio
        """
        # Mapear rol - manejar variantes como master_admin
        rol_str = modelo.role or 'user'
        if rol_str in ('master', 'master_admin'):
            rol = RolUsuario.MASTER
        elif rol_str == 'admin':
            rol = RolUsuario.ADMIN
        elif rol_str == 'viewer':
            rol = RolUsuario.VIEWER
        else:
            rol = RolUsuario.USER

        # Mapear estado - active es booleano en BD
        if modelo.locked_until and modelo.locked_until > datetime.now():
            estado = EstadoUsuario.BLOQUEADO
        elif modelo.active:
            estado = EstadoUsuario.ACTIVO
        else:
            estado = EstadoUsuario.INACTIVO

        return Usuario(
            id=modelo.id,
            nombre_usuario=modelo.username,
            correo=modelo.email,
            contrasena_cifrada=modelo.password_hash,
            nombre_completo=modelo.full_name or modelo.username,
            rol=rol,
            estado=estado,
            foto_perfil=modelo.profile_picture,
            intentos_fallidos=modelo.login_attempts or 0,
            bloqueado_hasta=modelo.locked_until,
            ultimo_acceso=modelo.last_login,
            fecha_creacion=modelo.created_at,
            fecha_actualizacion=modelo.updated_at,
            id_trabajador=modelo.trabajador_id,
            forzar_cambio_contrasena=modelo.force_password_change or False,
        )

    def _a_modelo(self, entidad: Usuario) -> ModeloUsuario:
        """
        Convierte una entidad de dominio a modelo de SQLAlchemy.

        Args:
            entidad: Entidad de dominio

        Returns:
            Modelo de persistencia
        """
        return ModeloUsuario(
            username=entidad.nombre_usuario,
            email=entidad.correo,
            password_hash=entidad.contrasena_cifrada,
            full_name=entidad.nombre_completo,
            role=entidad.rol.value,
            active=entidad.estado == EstadoUsuario.ACTIVO,
            profile_picture=entidad.foto_perfil,
            login_attempts=entidad.intentos_fallidos,
            locked_until=entidad.bloqueado_hasta,
            last_login=entidad.ultimo_acceso,
            created_at=entidad.fecha_creacion,
            updated_at=entidad.fecha_actualizacion,
            trabajador_id=entidad.id_trabajador,
        )

    def _actualizar_modelo(self, modelo: ModeloUsuario, entidad: Usuario) -> None:
        """
        Actualiza un modelo con los datos de una entidad.

        Args:
            modelo: Modelo a actualizar
            entidad: Entidad con los nuevos datos
        """
        modelo.username = entidad.nombre_usuario
        modelo.email = entidad.correo
        modelo.password_hash = entidad.contrasena_cifrada
        modelo.full_name = entidad.nombre_completo
        modelo.role = entidad.rol.value
        modelo.active = entidad.estado == EstadoUsuario.ACTIVO
        modelo.profile_picture = entidad.foto_perfil
        modelo.login_attempts = entidad.intentos_fallidos
        modelo.locked_until = entidad.bloqueado_hasta
        modelo.last_login = entidad.ultimo_acceso
        modelo.updated_at = datetime.now()
        modelo.trabajador_id = entidad.id_trabajador
        modelo.force_password_change = entidad.forzar_cambio_contrasena
