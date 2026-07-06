# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CHAT - IMPLEMENTACIONES DE BUSQUEDA                       ║
║                        Elasticsearch como Backend                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

██████████████████████████████████████████████████████████████████████████████
██  REGLAS PARA ESTA CAPA (APLICA A TODOS LOS MODULOS)                       ██
██████████████████████████████████████████████████████████████████████████████

1. RESPONSABILIDADES:
   - Implementar interfaces de dominio/repositorios/repositorio_busqueda.py
   - Manejar conexion a Elasticsearch
   - Configurar mappings e indices
   - Gestionar busquedas full-text

2. DEPENDENCIAS PERMITIDAS:
   - dominio/ (interfaces y entidades)
   - elasticsearch (cliente oficial)

3. DEPENDENCIAS PROHIBIDAS:
   - Flask (va en interfaces/)
   - SQLAlchemy (va en persistencia/)
   - aplicacion/ (no debe conocer casos de uso)

4. INDICE PRINCIPAL:
   - chat_mensajes : Mensajes de chat con full-text search

MAPPING:
{
    "contenido": {"type": "text", "analyzer": "spanish"},
    "conversacion_id": {"type": "keyword"},
    "remitente_id": {"type": "keyword"},
    "participantes": {"type": "keyword"},  # Array para permisos
    "tipo": {"type": "keyword"},
    "creado_en": {"type": "date"}
}

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

from .cliente_elasticsearch import (
    ClienteElasticsearch,
    obtener_cliente_elasticsearch,
)
from .buscador_mensajes import BuscadorMensajesElasticsearch
from .indexador_mensajes import IndexadorMensajesElasticsearch
from .administrador_indice import AdministradorIndiceElasticsearch

__all__ = [
    # Cliente base
    'ClienteElasticsearch',
    'obtener_cliente_elasticsearch',
    # Implementaciones
    'BuscadorMensajesElasticsearch',
    'IndexadorMensajesElasticsearch',
    'AdministradorIndiceElasticsearch',
]
