# -*- coding: utf-8 -*-
"""
Módulo Usuarios - Sistema FARO

Módulo de gestión de usuarios siguiendo arquitectura hexagonal.

ESTRUCTURA:
    modulos/usuarios/
    ├── dominio/           # Lógica de negocio pura
    │   ├── entidades/     # Usuario, RolUsuario, EstadoUsuario
    │   ├── repositorios/  # IRepositorioUsuario (interfaces)
    │   ├── excepciones/   # Excepciones de dominio
    │   └── value_objects/ # Contrasena, CorreoElectronico
    ├── aplicacion/        # Casos de uso y DTOs
    │   └── dtos/          # UsuarioDTO, CrearUsuarioDTO, etc.
    ├── infraestructura/   # Implementaciones técnicas
    │   └── persistencia/  # RepositorioUsuarioPostgreSQL, ModeloUsuario
    └── interfaces/        # Adaptadores de entrada (API, Web)

USO:
    # Importar entidades
    from modulos.usuarios import Usuario, RolUsuario, EstadoUsuario

    # Importar repositorios
    from modulos.usuarios import IRepositorioUsuario, RepositorioUsuarioPostgreSQL

    # Importar DTOs
    from modulos.usuarios import UsuarioDTO, CrearUsuarioDTO

    # Importar value objects
    from modulos.usuarios import Contrasena, CorreoElectronico

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-04
"""

# ═══════════════════════════════════════════════════════════════════
# DOMINIO - Entidades
# ═══════════════════════════════════════════════════════════════════
from modulos.usuarios.dominio.entidades import (
    Usuario,
    RolUsuario,
    EstadoUsuario,
)

# ═══════════════════════════════════════════════════════════════════
# DOMINIO - Repositorios (Interfaces/Puertos)
# ═══════════════════════════════════════════════════════════════════
from modulos.usuarios.dominio.repositorios import (
    IRepositorioBase,
    IRepositorioUsuario,
)

# ═══════════════════════════════════════════════════════════════════
# DOMINIO - Value Objects
# ═══════════════════════════════════════════════════════════════════
from modulos.usuarios.dominio.value_objects import (
    Contrasena,
    CorreoElectronico,
)

# ═══════════════════════════════════════════════════════════════════
# DOMINIO - Excepciones
# ═══════════════════════════════════════════════════════════════════
from modulos.usuarios.dominio.excepciones import (
    ExcepcionDominio,
    ExcepcionValidacion,
    ExcepcionNoEncontrado,
    ExcepcionDuplicado,
    UsuarioNoEncontradoError,
    NombreUsuarioDuplicadoError,
    CorreoDuplicadoError,
    ContrasenaDebilError,
)

# ═══════════════════════════════════════════════════════════════════
# APLICACIÓN - DTOs
# ═══════════════════════════════════════════════════════════════════
from modulos.usuarios.aplicacion.dtos import (
    UsuarioDTO,
    CrearUsuarioDTO,
    ActualizarUsuarioDTO,
    ResultadoDTO,
)

# ═══════════════════════════════════════════════════════════════════
# INFRAESTRUCTURA - Repositorios y Modelos
# ═══════════════════════════════════════════════════════════════════
from modulos.usuarios.infraestructura.persistencia import (
    RepositorioUsuarioPostgreSQL,
    ModeloUsuario,
)

# ═══════════════════════════════════════════════════════════════════
# EXPORTS PÚBLICOS
# ═══════════════════════════════════════════════════════════════════
__all__ = [
    # Entidades
    'Usuario',
    'RolUsuario',
    'EstadoUsuario',
    # Repositorios (Interfaces)
    'IRepositorioBase',
    'IRepositorioUsuario',
    # Repositorios (Implementaciones)
    'RepositorioUsuarioPostgreSQL',
    # Modelos
    'ModeloUsuario',
    # Value Objects
    'Contrasena',
    'CorreoElectronico',
    # DTOs
    'UsuarioDTO',
    'CrearUsuarioDTO',
    'ActualizarUsuarioDTO',
    'ResultadoDTO',
    # Excepciones
    'ExcepcionDominio',
    'ExcepcionValidacion',
    'ExcepcionNoEncontrado',
    'ExcepcionDuplicado',
    'UsuarioNoEncontradoError',
    'NombreUsuarioDuplicadoError',
    'CorreoDuplicadoError',
    'ContrasenaDebilError',
]
