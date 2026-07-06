# -*- coding: utf-8 -*-
"""
Base de Datos: Configuracion Base - Compartido

Define la base declarativa de SQLAlchemy y funciones
de inicializacion de la base de datos.

CAPA: compartido/infraestructura/base_datos
REGLAS:
- Codigo compartido entre todos los modulos
- No depende de ningun modulo especifico

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado a compartido: 2026-01-05
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator
import os

# Base declarativa para todos los modelos
Base = declarative_base()


class GestorBaseDatos:
    """
    Gestor de conexion a la base de datos.

    Centraliza la creacion de conexiones y sesiones.

    Ejemplo:
        gestor = GestorBaseDatos("postgresql://user:pass@localhost/db")
        with gestor.obtener_session() as session:
            usuarios = session.query(ModeloUsuario).all()
    """

    def __init__(self, url_conexion: str = None):
        """
        Inicializa el gestor de base de datos.

        Args:
            url_conexion: URL de conexion SQLAlchemy.
                         Si no se proporciona, usa DATABASE_URL del entorno.
        """
        self._url = url_conexion or os.getenv('DATABASE_URL')
        if not self._url:
            raise ValueError(
                "Se requiere URL de conexion. "
                "Proporcione url_conexion o configure DATABASE_URL"
            )

        self._engine = create_engine(
            self._url,
            pool_size=2,           # Reducido para multi-worker (evitar agotamiento)
            max_overflow=3,        # Reducido para limitar conexiones máximas
            pool_pre_ping=True,    # Verifica conexiones antes de usar
            pool_recycle=1800,     # Recicla conexiones cada 30 min
            pool_timeout=30,       # Timeout para obtener conexión
            echo=os.getenv('SQL_ECHO', 'false').lower() == 'true'
        )

        self._SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._engine
        )

    def crear_tablas(self) -> None:
        """
        Crea todas las tablas definidas en los modelos.

        Solo para desarrollo. En produccion usar migraciones.
        """
        Base.metadata.create_all(bind=self._engine)

    def eliminar_tablas(self) -> None:
        """
        Elimina todas las tablas.

        PELIGRO: Solo para desarrollo/pruebas.
        """
        Base.metadata.drop_all(bind=self._engine)

    def obtener_session(self) -> Generator[Session, None, None]:
        """
        Genera una sesion de base de datos.

        Uso con context manager:
            with gestor.obtener_session() as session:
                # usar session

        Yields:
            Sesion de SQLAlchemy
        """
        session = self._SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def session(self) -> Session:
        """
        Retorna una nueva sesion (sin context manager).

        El llamador es responsable de cerrar la sesion.

        Returns:
            Nueva sesion de SQLAlchemy
        """
        return self._SessionLocal()

    @property
    def engine(self):
        """Retorna el engine de SQLAlchemy."""
        return self._engine


# Instancia global (se configura al inicio de la aplicacion)
_gestor_db: GestorBaseDatos = None


def inicializar_base_datos(url_conexion: str = None) -> GestorBaseDatos:
    """
    Inicializa la conexion a la base de datos.

    Args:
        url_conexion: URL de conexion SQLAlchemy

    Returns:
        Gestor de base de datos configurado
    """
    global _gestor_db
    _gestor_db = GestorBaseDatos(url_conexion)
    return _gestor_db


def obtener_gestor() -> GestorBaseDatos:
    """
    Obtiene el gestor de base de datos.

    Returns:
        Gestor de base de datos

    Raises:
        RuntimeError: Si no se ha inicializado
    """
    if _gestor_db is None:
        raise RuntimeError(
            "Base de datos no inicializada. "
            "Llame a inicializar_base_datos() primero."
        )
    return _gestor_db


def obtener_session() -> Generator[Session, None, None]:
    """
    Funcion de conveniencia para obtener una sesion.

    Yields:
        Sesion de SQLAlchemy
    """
    return obtener_gestor().obtener_session()
