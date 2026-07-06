# -*- coding: utf-8 -*-
"""
Indexador de Mensajes - Implementacion Elasticsearch

Indexa mensajes para busqueda full-text.

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

import logging
from typing import Optional, List, Dict, Any

from ...dominio.repositorios.repositorio_busqueda import IndexadorMensajes
from .cliente_elasticsearch import ClienteElasticsearch, obtener_cliente_elasticsearch

logger = logging.getLogger(__name__)


class IndexadorMensajesElasticsearch(IndexadorMensajes):
    """
    Implementacion Elasticsearch del indexador de mensajes.

    Caracteristicas:
    - Indexacion individual y en batch
    - Actualizacion parcial de documentos
    - Eliminacion logica y fisica
    """

    INDICE = "chat_mensajes"

    def __init__(self, cliente: Optional[ClienteElasticsearch] = None):
        """
        Inicializa el indexador.

        Args:
            cliente: Cliente Elasticsearch (usa singleton si no se proporciona)
        """
        self._es = cliente or obtener_cliente_elasticsearch()

    def indexar(self, mensaje: Dict[str, Any]) -> bool:
        """
        Indexa un mensaje nuevo.
        """
        if not self._es.disponible:
            return False

        try:
            # Preparar documento
            documento = self._preparar_documento(mensaje)

            # Indexar
            resultado = self._es.indexar(
                indice=self.INDICE,
                documento=documento,
                id_documento=str(mensaje.get("id"))
            )

            if resultado:
                logger.debug(f"Mensaje {mensaje.get('id')} indexado")

            return resultado

        except Exception as e:
            logger.error(f"Error indexando mensaje: {e}")
            return False

    def indexar_lote(self, mensajes: List[Dict[str, Any]]) -> int:
        """
        Indexa multiples mensajes en batch.
        """
        if not self._es.disponible or not mensajes:
            return 0

        try:
            # Preparar documentos
            documentos = [self._preparar_documento(m) for m in mensajes]

            # Bulk indexar
            indexados = self._es.bulk_indexar(
                indice=self.INDICE,
                documentos=documentos,
                campo_id="id"
            )

            logger.info(f"Indexados {indexados}/{len(mensajes)} mensajes en batch")
            return indexados

        except Exception as e:
            logger.error(f"Error en indexacion batch: {e}")
            return 0

    def actualizar(
        self,
        mensaje_id: int,
        campos: Dict[str, Any]
    ) -> bool:
        """
        Actualiza un mensaje en el indice.
        """
        if not self._es.disponible:
            return False

        try:
            # Filtrar campos validos
            campos_validos = {
                k: v for k, v in campos.items()
                if k in ["contenido", "editado_en", "activo", "tipo"]
            }

            if not campos_validos:
                return True

            resultado = self._es.actualizar(
                indice=self.INDICE,
                id_documento=str(mensaje_id),
                campos=campos_validos
            )

            if resultado:
                logger.debug(f"Mensaje {mensaje_id} actualizado en indice")

            return resultado

        except Exception as e:
            logger.error(f"Error actualizando mensaje en indice: {e}")
            return False

    def eliminar(self, mensaje_id: int) -> bool:
        """
        Elimina un mensaje del indice.
        """
        if not self._es.disponible:
            return False

        try:
            resultado = self._es.eliminar(
                indice=self.INDICE,
                id_documento=str(mensaje_id)
            )

            if resultado:
                logger.debug(f"Mensaje {mensaje_id} eliminado del indice")

            return resultado

        except Exception as e:
            logger.error(f"Error eliminando mensaje del indice: {e}")
            return False

    def marcar_eliminado(self, mensaje_id: int) -> bool:
        """
        Marca un mensaje como eliminado (soft delete).
        """
        return self.actualizar(mensaje_id, {"activo": False})

    def eliminar_conversacion(self, conversacion_id: int) -> int:
        """
        Elimina todos los mensajes de una conversacion del indice.
        """
        if not self._es.disponible:
            return 0

        try:
            # Buscar todos los IDs de mensajes de la conversacion
            query = {"term": {"conversacion_id": conversacion_id}}

            resultado = self._es.buscar(
                indice=self.INDICE,
                query=query,
                size=10000  # Maximo
            )

            ids = [
                hit["_id"]
                for hit in resultado.get("hits", {}).get("hits", [])
            ]

            if not ids:
                return 0

            # Eliminar en batch
            eliminados = self._es.bulk_eliminar(
                indice=self.INDICE,
                ids=ids
            )

            logger.info(
                f"Eliminados {eliminados} mensajes de conv {conversacion_id}"
            )
            return eliminados

        except Exception as e:
            logger.error(f"Error eliminando conversacion del indice: {e}")
            return 0

    def reindexar_conversacion(
        self,
        conversacion_id: int,
        mensajes: List[Dict[str, Any]]
    ) -> int:
        """
        Reindexa todos los mensajes de una conversacion.
        """
        if not self._es.disponible:
            return 0

        try:
            # Primero eliminar mensajes existentes
            self.eliminar_conversacion(conversacion_id)

            # Luego indexar los nuevos
            return self.indexar_lote(mensajes)

        except Exception as e:
            logger.error(f"Error reindexando conversacion: {e}")
            return 0

    def _preparar_documento(self, mensaje: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepara un mensaje para ser indexado.

        Transforma el formato de la BD al formato de ES.
        """
        documento = {
            "id": mensaje.get("id"),
            "public_id": mensaje.get("public_id"),
            "conversacion_id": mensaje.get("conversacion_id"),
            "remitente_id": mensaje.get("remitente_id"),
            "contenido": mensaje.get("contenido", ""),
            "tipo": mensaje.get("tipo", "texto"),
            "creado_en": mensaje.get("creado_en"),
            "editado_en": mensaje.get("editado_en"),
            "activo": mensaje.get("activo", True),
            "participantes": mensaje.get("participantes", []),
        }

        # Procesar archivos si existen
        archivos = mensaje.get("archivos", [])
        if archivos:
            documento["tiene_archivos"] = True
            documento["archivos_nombres"] = " ".join(
                a.get("nombre_original", "") for a in archivos
            )
        else:
            documento["tiene_archivos"] = False
            documento["archivos_nombres"] = ""

        return documento
