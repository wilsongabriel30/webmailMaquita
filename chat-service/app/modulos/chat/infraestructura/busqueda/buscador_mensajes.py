# -*- coding: utf-8 -*-
"""
Buscador de Mensajes - Implementacion Elasticsearch

Busqueda full-text en mensajes de chat.
Latencia objetivo: < 50ms

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

import logging
import time
from typing import Optional, List, Dict, Any

from ...dominio.repositorios.repositorio_busqueda import (
    BuscadorMensajes,
    ResultadoBusqueda,
    FiltrosBusqueda,
)
from .cliente_elasticsearch import ClienteElasticsearch, obtener_cliente_elasticsearch

logger = logging.getLogger(__name__)


class BuscadorMensajesElasticsearch(BuscadorMensajes):
    """
    Implementacion Elasticsearch del buscador de mensajes.

    Caracteristicas:
    - Busqueda full-text con analizador español
    - Highlighting de resultados
    - Filtrado por permisos (solo mensajes donde el usuario es participante)
    - Paginacion eficiente
    """

    INDICE = "chat_mensajes"

    def __init__(self, cliente: Optional[ClienteElasticsearch] = None):
        """
        Inicializa el buscador.

        Args:
            cliente: Cliente Elasticsearch (usa singleton si no se proporciona)
        """
        self._es = cliente or obtener_cliente_elasticsearch()

    def buscar(self, filtros: FiltrosBusqueda) -> ResultadoBusqueda:
        """
        Busca mensajes segun los filtros.
        """
        inicio = time.time()

        if not self._es.disponible:
            return ResultadoBusqueda(
                mensajes=[],
                total=0,
                pagina=filtros.pagina,
                paginas_totales=0,
                tiempo_ms=0,
                query_original=filtros.query
            )

        # Construir query
        query = self._construir_query(filtros)

        # Calcular paginacion
        from_ = (filtros.pagina - 1) * filtros.por_pagina

        # Ejecutar busqueda
        resultado = self._es.buscar(
            indice=self.INDICE,
            query=query,
            size=filtros.por_pagina,
            from_=from_,
            sort=[{"creado_en": {"order": "desc"}}],
            highlight={
                "fields": {
                    "contenido": {
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"],
                        "fragment_size": 150,
                        "number_of_fragments": 3
                    }
                }
            }
        )

        # Procesar resultados
        hits = resultado.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        mensajes = self._procesar_hits(hits.get("hits", []))

        tiempo_ms = (time.time() - inicio) * 1000

        return ResultadoBusqueda(
            mensajes=mensajes,
            total=total,
            pagina=filtros.pagina,
            paginas_totales=(total + filtros.por_pagina - 1) // filtros.por_pagina,
            tiempo_ms=tiempo_ms,
            query_original=filtros.query
        )

    def buscar_en_conversacion(
        self,
        conversacion_id: int,
        query: str,
        usuario_id: int,
        limite: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Busqueda rapida dentro de una conversacion.
        """
        if not self._es.disponible:
            return []

        es_query = {
            "bool": {
                "must": [
                    {"match": {"contenido": query}},
                    {"term": {"conversacion_id": conversacion_id}},
                    {"term": {"participantes": usuario_id}},
                    {"term": {"activo": True}}
                ]
            }
        }

        resultado = self._es.buscar(
            indice=self.INDICE,
            query=es_query,
            size=limite,
            sort=[{"creado_en": {"order": "desc"}}],
            highlight={
                "fields": {
                    "contenido": {
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"]
                    }
                }
            }
        )

        return self._procesar_hits(resultado.get("hits", {}).get("hits", []))

    def buscar_global(
        self,
        usuario_id: int,
        query: str,
        limite: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Busqueda en todas las conversaciones del usuario.
        """
        if not self._es.disponible:
            return []

        es_query = {
            "bool": {
                "must": [
                    {"match": {"contenido": query}},
                    {"term": {"participantes": usuario_id}},
                    {"term": {"activo": True}}
                ]
            }
        }

        resultado = self._es.buscar(
            indice=self.INDICE,
            query=es_query,
            size=limite,
            sort=[
                {"_score": {"order": "desc"}},
                {"creado_en": {"order": "desc"}}
            ],
            highlight={
                "fields": {
                    "contenido": {
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"],
                        "fragment_size": 150
                    }
                }
            }
        )

        return self._procesar_hits(resultado.get("hits", {}).get("hits", []))

    def sugerir(
        self,
        usuario_id: int,
        prefijo: str,
        limite: int = 10
    ) -> List[str]:
        """
        Sugiere terminos de busqueda basado en un prefijo.
        """
        if not self._es.disponible or len(prefijo) < 2:
            return []

        # Buscar mensajes que contengan el prefijo
        es_query = {
            "bool": {
                "must": [
                    {
                        "match_phrase_prefix": {
                            "contenido": {
                                "query": prefijo,
                                "max_expansions": 50
                            }
                        }
                    },
                    {"term": {"participantes": usuario_id}},
                    {"term": {"activo": True}}
                ]
            }
        }

        resultado = self._es.buscar(
            indice=self.INDICE,
            query=es_query,
            size=limite
        )

        # Extraer palabras unicas que comienzan con el prefijo
        sugerencias = set()
        prefijo_lower = prefijo.lower()

        for hit in resultado.get("hits", {}).get("hits", []):
            contenido = hit.get("_source", {}).get("contenido", "")
            palabras = contenido.lower().split()

            for palabra in palabras:
                if palabra.startswith(prefijo_lower) and len(palabra) > len(prefijo):
                    sugerencias.add(palabra)
                    if len(sugerencias) >= limite:
                        break

        return list(sugerencias)[:limite]

    def _construir_query(self, filtros: FiltrosBusqueda) -> Dict[str, Any]:
        """Construye la query de Elasticsearch."""
        must = [
            {"term": {"participantes": filtros.usuario_id}},
            {"term": {"activo": True}}
        ]

        # Texto de busqueda
        if filtros.query:
            must.append({
                "multi_match": {
                    "query": filtros.query,
                    "fields": ["contenido^3", "archivos_nombres"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            })

        # Filtro por conversacion
        if filtros.conversacion_id:
            must.append({"term": {"conversacion_id": filtros.conversacion_id}})

        # Filtro por remitente
        if filtros.remitente_id:
            must.append({"term": {"remitente_id": filtros.remitente_id}})

        # Filtro por tipo
        if filtros.tipo_mensaje:
            must.append({"term": {"tipo": filtros.tipo_mensaje.value}})

        # Filtro solo con archivos
        if filtros.solo_con_archivos:
            must.append({"term": {"tiene_archivos": True}})

        # Filtro por fecha
        if filtros.fecha_desde or filtros.fecha_hasta:
            rango = {}
            if filtros.fecha_desde:
                rango["gte"] = filtros.fecha_desde.isoformat()
            if filtros.fecha_hasta:
                rango["lte"] = filtros.fecha_hasta.isoformat()
            must.append({"range": {"creado_en": rango}})

        return {"bool": {"must": must}}

    def _procesar_hits(self, hits: List[Dict]) -> List[Dict[str, Any]]:
        """Procesa los hits de Elasticsearch."""
        mensajes = []

        for hit in hits:
            mensaje = hit.get("_source", {}).copy()
            mensaje["_score"] = hit.get("_score", 0)

            # Agregar highlighting si existe
            if "highlight" in hit:
                mensaje["_highlight"] = hit["highlight"].get("contenido", [])

            mensajes.append(mensaje)

        return mensajes
