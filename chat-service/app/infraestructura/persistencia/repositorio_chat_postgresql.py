# -*- coding: utf-8 -*-
"""
Repositorios Chat PostgreSQL - BRIDGE LEGACY

NOTA: Este archivo es un bridge de compatibilidad.
El codigo real esta en: modulos/chat/infraestructura/persistencia/repositorio_chat_postgresql.py

Para nuevo codigo, usar:
    from modulos.chat.infraestructura.persistencia import RepositorioConversacionPostgreSQL

Autor: Wilson Arguello
Migrado: 2026-01-05
"""

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
