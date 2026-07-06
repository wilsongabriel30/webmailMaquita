# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     CHAT - CAPA DE INFRAESTRUCTURA                           ║
║                   Implementaciones Tecnicas Concretas                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

██████████████████████████████████████████████████████████████████████████████
██  REGLAS PARA ESTA CAPA (APLICA A TODOS LOS MODULOS)                       ██
██████████████████████████████████████████████████████████████████████████████

1. RESPONSABILIDADES:
   - Implementar las INTERFACES definidas en dominio/repositorios/
   - Conectar con tecnologias externas (PostgreSQL, Redis, APIs)
   - Traducir entre modelos de dominio y modelos de persistencia
   - Manejar detalles tecnicos (conexiones, transacciones, cache)

2. DEPENDENCIAS PERMITIDAS:
   - dominio/ (para implementar interfaces y usar entidades)
   - Librerias externas: SQLAlchemy, Redis, requests, etc.

3. DEPENDENCIAS PROHIBIDAS:
   - Flask (eso va en interfaces/)
   - aplicacion/ (no debe conocer casos de uso)

4. ESTRUCTURA TIPICA:
   infraestructura/
   ├── persistencia/      # Repositorios PostgreSQL
   │   ├── modelos/       # Modelos SQLAlchemy
   │   └── repositorios/  # Implementaciones de interfaces
   ├── cache/             # Implementaciones Redis
   └── externos/          # Integraciones APIs terceros

5. EJEMPLO DE REPOSITORIO CORRECTO:

   from dominio.repositorios import RepositorioMensaje  # Interface
   from dominio.entidades import Mensaje                 # Entidad
   from sqlalchemy.orm import Session

   class RepositorioMensajePostgreSQL(RepositorioMensaje):
       def __init__(self, session: Session):
           self._session = session

       def crear(self, mensaje: Mensaje) -> Mensaje:
           modelo = MensajeModelo.from_entidad(mensaje)
           self._session.add(modelo)
           self._session.flush()
           return modelo.to_entidad()

6. PATRON: ADAPTER
   Esta capa actua como ADAPTADOR entre el dominio y las tecnologias.
   El dominio define QUE necesita, infraestructura define COMO se hace.

██████████████████████████████████████████████████████████████████████████████

Contenido actual:
- persistencia/ : Repositorios PostgreSQL (SQLAlchemy)
- cache/        : Cache Redis (mensajes, presencia, sesiones)
- busqueda/     : Elasticsearch (full-text search)
- (futuro) externos/ : APIs de terceros
"""

from .persistencia import (
    RepositorioConversacionPostgreSQL,
    RepositorioParticipantePostgreSQL,
    RepositorioMensajePostgreSQL,
    RepositorioArchivoMensajePostgreSQL,
    RepositorioReaccionPostgreSQL,
    RepositorioPresenciaPostgreSQL,
    RepositorioBloqueoPostgreSQL,
    RepositorioIndicadorAccionPostgreSQL,
)

from .cache import (
    ClienteRedis,
    obtener_cliente_redis,
    CacheMensajesRedis,
    CachePresenciaRedis,
    CacheIndicadorAccionRedis,
    CacheConversacionRedis,
    CacheSesionWebSocketRedis,
)

from .busqueda import (
    ClienteElasticsearch,
    obtener_cliente_elasticsearch,
    BuscadorMensajesElasticsearch,
    IndexadorMensajesElasticsearch,
    AdministradorIndiceElasticsearch,
)

__all__ = [
    # Persistencia PostgreSQL
    'RepositorioConversacionPostgreSQL',
    'RepositorioParticipantePostgreSQL',
    'RepositorioMensajePostgreSQL',
    'RepositorioArchivoMensajePostgreSQL',
    'RepositorioReaccionPostgreSQL',
    'RepositorioPresenciaPostgreSQL',
    'RepositorioBloqueoPostgreSQL',
    'RepositorioIndicadorAccionPostgreSQL',
    # Cache Redis
    'ClienteRedis',
    'obtener_cliente_redis',
    'CacheMensajesRedis',
    'CachePresenciaRedis',
    'CacheIndicadorAccionRedis',
    'CacheConversacionRedis',
    'CacheSesionWebSocketRedis',
    # Busqueda Elasticsearch
    'ClienteElasticsearch',
    'obtener_cliente_elasticsearch',
    'BuscadorMensajesElasticsearch',
    'IndexadorMensajesElasticsearch',
    'AdministradorIndiceElasticsearch',
]
