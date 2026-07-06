# -*- coding: utf-8 -*-
"""
Contenedor de Inyección de Dependencias

Centraliza la creación y configuración de todas las dependencias
del sistema, permitiendo intercambiar implementaciones fácilmente.

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session

from dominio.repositorios.i_repositorio_usuario import IRepositorioUsuario
from dominio.servicios.servicio_autenticacion import (
    ServicioAutenticacion,
    ICifradorContrasena,
)
from infraestructura.persistencia.repositorio_usuario_postgresql import (
    RepositorioUsuarioPostgreSQL,
)
from infraestructura.seguridad.cifrador_bcrypt import CifradorBcrypt
from aplicacion.casos_uso.autenticar_usuario import AutenticarUsuario
from aplicacion.casos_uso.cambiar_contrasena import CambiarContrasena


@dataclass
class Contenedor:
    """
    Contenedor de dependencias del sistema.

    Centraliza la creación de todas las dependencias,
    facilitando:
    - Inyección de dependencias
    - Pruebas unitarias (intercambiar por mocks)
    - Configuración por ambiente

    Ejemplo:
        contenedor = Contenedor.crear(session)
        resultado = contenedor.caso_autenticar.ejecutar(login_dto)
    """

    # Repositorios
    repositorio_usuario: IRepositorioUsuario

    # Servicios de infraestructura
    cifrador: ICifradorContrasena

    # Servicios de dominio
    servicio_autenticacion: ServicioAutenticacion

    # Casos de uso
    caso_autenticar: AutenticarUsuario
    caso_cambiar_contrasena: CambiarContrasena

    @classmethod
    def crear(
        cls,
        session: Session,
        cifrador: Optional[ICifradorContrasena] = None
    ) -> 'Contenedor':
        """
        Crea un contenedor con todas las dependencias configuradas.

        Args:
            session: Sesión de SQLAlchemy
            cifrador: Cifrador personalizado (opcional)

        Returns:
            Contenedor configurado
        """
        # Adaptadores de infraestructura
        _cifrador = cifrador or CifradorBcrypt()
        _repositorio_usuario = RepositorioUsuarioPostgreSQL(session)

        # Servicios de dominio
        _servicio_autenticacion = ServicioAutenticacion(_cifrador)

        # Casos de uso
        _caso_autenticar = AutenticarUsuario(
            repositorio_usuario=_repositorio_usuario,
            servicio_autenticacion=_servicio_autenticacion
        )

        _caso_cambiar_contrasena = CambiarContrasena(
            repositorio_usuario=_repositorio_usuario,
            servicio_autenticacion=_servicio_autenticacion
        )

        return cls(
            repositorio_usuario=_repositorio_usuario,
            cifrador=_cifrador,
            servicio_autenticacion=_servicio_autenticacion,
            caso_autenticar=_caso_autenticar,
            caso_cambiar_contrasena=_caso_cambiar_contrasena,
        )

    @classmethod
    def crear_para_pruebas(
        cls,
        repositorio_usuario: Optional[IRepositorioUsuario] = None,
        cifrador: Optional[ICifradorContrasena] = None
    ) -> 'Contenedor':
        """
        Crea un contenedor para pruebas unitarias.

        Permite inyectar mocks de los repositorios y servicios.

        Args:
            repositorio_usuario: Mock del repositorio (opcional)
            cifrador: Mock del cifrador (opcional)

        Returns:
            Contenedor configurado para pruebas
        """
        from unittest.mock import MagicMock

        _repositorio = repositorio_usuario or MagicMock(spec=IRepositorioUsuario)
        _cifrador = cifrador or MagicMock(spec=ICifradorContrasena)

        _servicio_autenticacion = ServicioAutenticacion(_cifrador)

        _caso_autenticar = AutenticarUsuario(
            repositorio_usuario=_repositorio,
            servicio_autenticacion=_servicio_autenticacion
        )

        _caso_cambiar_contrasena = CambiarContrasena(
            repositorio_usuario=_repositorio,
            servicio_autenticacion=_servicio_autenticacion
        )

        return cls(
            repositorio_usuario=_repositorio,
            cifrador=_cifrador,
            servicio_autenticacion=_servicio_autenticacion,
            caso_autenticar=_caso_autenticar,
            caso_cambiar_contrasena=_caso_cambiar_contrasena,
        )
