# -*- coding: utf-8 -*-
"""
Administrador de Indice - Implementacion Elasticsearch

Gestiona el ciclo de vida de los indices de busqueda.

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

import logging
from typing import Optional, Dict, Any

from ...dominio.repositorios.repositorio_busqueda import AdministradorIndice
from .cliente_elasticsearch import ClienteElasticsearch, obtener_cliente_elasticsearch

logger = logging.getLogger(__name__)


class AdministradorIndiceElasticsearch(AdministradorIndice):
    """
    Implementacion Elasticsearch del administrador de indices.

    Funciones:
    - Crear/eliminar indices
    - Configurar mappings
    - Obtener estadisticas
    - Optimizar indices
    """

    def __init__(self, cliente: Optional[ClienteElasticsearch] = None):
        """
        Inicializa el administrador.

        Args:
            cliente: Cliente Elasticsearch (usa singleton si no se proporciona)
        """
        self._es = cliente or obtener_cliente_elasticsearch()

    def crear_indice(
        self,
        nombre: str,
        configuracion: Dict[str, Any]
    ) -> bool:
        """
        Crea un nuevo indice.
        """
        if not self._es.disponible:
            return False

        try:
            if self._es.existe_indice(nombre):
                logger.warning(f"El indice '{nombre}' ya existe")
                return True

            resultado = self._es.crear_indice(nombre, configuracion)

            if resultado:
                logger.info(f"Indice '{nombre}' creado exitosamente")

            return resultado

        except Exception as e:
            logger.error(f"Error creando indice '{nombre}': {e}")
            return False

    def existe_indice(self, nombre: str) -> bool:
        """
        Verifica si un indice existe.
        """
        return self._es.existe_indice(nombre)

    def eliminar_indice(self, nombre: str) -> bool:
        """
        Elimina un indice.
        """
        if not self._es.disponible:
            return False

        try:
            if not self._es.existe_indice(nombre):
                logger.warning(f"El indice '{nombre}' no existe")
                return True

            resultado = self._es.eliminar_indice(nombre)

            if resultado:
                logger.info(f"Indice '{nombre}' eliminado exitosamente")

            return resultado

        except Exception as e:
            logger.error(f"Error eliminando indice '{nombre}': {e}")
            return False

    def obtener_estadisticas(self, nombre: str) -> Dict[str, Any]:
        """
        Obtiene estadisticas del indice.
        """
        if not self._es.disponible:
            return {"disponible": False}

        try:
            stats = self._es.estadisticas(nombre)

            if not stats:
                return {"disponible": True, "existe": False}

            # Extraer metricas relevantes
            primaries = stats.get("primaries", {})
            docs = primaries.get("docs", {})
            store = primaries.get("store", {})

            return {
                "disponible": True,
                "existe": True,
                "documentos": docs.get("count", 0),
                "documentos_eliminados": docs.get("deleted", 0),
                "tamaño_bytes": store.get("size_in_bytes", 0),
                "tamaño_legible": self._formatear_bytes(
                    store.get("size_in_bytes", 0)
                ),
            }

        except Exception as e:
            logger.error(f"Error obteniendo estadisticas de '{nombre}': {e}")
            return {"disponible": True, "error": str(e)}

    def refrescar(self, nombre: str) -> bool:
        """
        Refresca el indice (hace documentos buscables).
        """
        if not self._es.disponible:
            return False

        try:
            resultado = self._es.refrescar(nombre)

            if resultado:
                logger.debug(f"Indice '{nombre}' refrescado")

            return resultado

        except Exception as e:
            logger.error(f"Error refrescando indice '{nombre}': {e}")
            return False

    def optimizar(self, nombre: str) -> bool:
        """
        Optimiza el indice (merge segments).
        """
        if not self._es.disponible:
            return False

        try:
            # Force merge para reducir segmentos
            if self._es.cliente:
                self._es.cliente.indices.forcemerge(
                    index=nombre,
                    max_num_segments=1
                )
                logger.info(f"Indice '{nombre}' optimizado")
                return True
            return False

        except Exception as e:
            logger.error(f"Error optimizando indice '{nombre}': {e}")
            return False

    def crear_indice_mensajes(self) -> bool:
        """
        Crea el indice de mensajes con la configuracion predefinida.
        """
        return self.crear_indice(
            nombre=self._es.INDICE_MENSAJES,
            configuracion=self._es.MAPPING_MENSAJES
        )

    def recrear_indice_mensajes(self) -> bool:
        """
        Elimina y recrea el indice de mensajes.
        PELIGROSO: Elimina todos los datos indexados.
        """
        logger.warning("Recreando indice de mensajes - ESTO ELIMINA TODOS LOS DATOS")

        # Eliminar si existe
        if self.existe_indice(self._es.INDICE_MENSAJES):
            if not self.eliminar_indice(self._es.INDICE_MENSAJES):
                return False

        # Crear nuevo
        return self.crear_indice_mensajes()

    def obtener_estado_salud(self) -> Dict[str, Any]:
        """
        Obtiene el estado de salud del cluster.
        """
        if not self._es.disponible:
            return {
                "disponible": False,
                "razon": "Elasticsearch no disponible"
            }

        try:
            if self._es.cliente:
                salud = self._es.cliente.cluster.health()
                return {
                    "disponible": True,
                    "cluster_name": salud.get("cluster_name"),
                    "status": salud.get("status"),  # green, yellow, red
                    "numero_nodos": salud.get("number_of_nodes"),
                    "numero_shards": salud.get("active_shards"),
                    "shards_no_asignados": salud.get("unassigned_shards"),
                }
            return {"disponible": False}

        except Exception as e:
            logger.error(f"Error obteniendo salud del cluster: {e}")
            return {"disponible": True, "error": str(e)}

    def _formatear_bytes(self, bytes_: int) -> str:
        """Formatea bytes a formato legible."""
        for unidad in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_ < 1024:
                return f"{bytes_:.2f} {unidad}"
            bytes_ /= 1024
        return f"{bytes_:.2f} PB"
