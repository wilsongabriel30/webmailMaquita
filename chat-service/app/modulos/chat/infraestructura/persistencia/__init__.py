# -*- coding: utf-8 -*-
"""
Chat - Persistencia PostgreSQL

Implementaciones de repositorios usando SQLAlchemy.

CAPA: infraestructura/persistencia

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado: 2026-01-05
"""

# Importar desde ubicacion local (100% hexagonal)
from modulos.chat.infraestructura.persistencia.repositorio_chat_postgresql import (
    RepositorioConversacionPostgreSQL,
    RepositorioParticipantePostgreSQL,
    RepositorioMensajePostgreSQL,
    RepositorioArchivoMensajePostgreSQL,
    RepositorioReaccionPostgreSQL,
    RepositorioPresenciaPostgreSQL,
    RepositorioBloqueoPostgreSQL,
    RepositorioIndicadorAccionPostgreSQL,
)

__all__ = [
    'RepositorioConversacionPostgreSQL',
    'RepositorioParticipantePostgreSQL',
    'RepositorioMensajePostgreSQL',
    'RepositorioArchivoMensajePostgreSQL',
    'RepositorioReaccionPostgreSQL',
    'RepositorioPresenciaPostgreSQL',
    'RepositorioBloqueoPostgreSQL',
    'RepositorioIndicadorAccionPostgreSQL',
]
