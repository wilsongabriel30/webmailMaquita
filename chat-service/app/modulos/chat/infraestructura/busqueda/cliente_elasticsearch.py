# -*- coding: utf-8 -*-
"""
Cliente Elasticsearch - Conexion y Utilidades Base

Maneja la conexion a Elasticsearch y proporciona utilidades comunes.

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

import os
import logging
from typing import Optional, Dict, Any, List

try:
    from elasticsearch import Elasticsearch, helpers
    ES_DISPONIBLE = True
except ImportError:
    ES_DISPONIBLE = False
    Elasticsearch = None
    helpers = None

logger = logging.getLogger(__name__)

# Singleton
_cliente: Optional['ClienteElasticsearch'] = None


class ClienteElasticsearch:
    """
    Cliente Elasticsearch con manejo de errores.

    Caracteristicas:
    - Conexion con retry automatico
    - Fallback silencioso si ES no esta disponible
    - Helpers para operaciones comunes
    """

    # Nombre del indice principal
    INDICE_MENSAJES = "chat_mensajes"

    # Mapping del indice de mensajes
    MAPPING_MENSAJES = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "spanish_custom": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",
                            "spanish_stop",
                            "spanish_stemmer"
                        ]
                    }
                },
                "filter": {
                    "spanish_stop": {
                        "type": "stop",
                        "stopwords": "_spanish_"
                    },
                    "spanish_stemmer": {
                        "type": "stemmer",
                        "language": "spanish"
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "id": {"type": "integer"},
                "public_id": {"type": "keyword"},
                "conversacion_id": {"type": "integer"},
                "remitente_id": {"type": "integer"},
                "participantes": {"type": "integer"},  # Array de IDs
                "contenido": {
                    "type": "text",
                    "analyzer": "spanish_custom",
                    "fields": {
                        "exact": {"type": "keyword"}
                    }
                },
                "tipo": {"type": "keyword"},
                "tiene_archivos": {"type": "boolean"},
                "archivos_nombres": {"type": "text"},
                "creado_en": {"type": "date"},
                "editado_en": {"type": "date"},
                "activo": {"type": "boolean"}
            }
        }
    }

    def __init__(
        self,
        hosts: Optional[List[str]] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_ssl: bool = False,
        verify_certs: bool = True,
        timeout: int = 30
    ):
        """
        Inicializa el cliente Elasticsearch.

        Args:
            hosts: Lista de hosts (default: ['localhost:9200'])
            username: Usuario para autenticacion
            password: Contraseña
            use_ssl: Usar HTTPS
            verify_certs: Verificar certificados SSL
            timeout: Timeout en segundos
        """
        self._disponible = ES_DISPONIBLE
        self._es: Optional[Elasticsearch] = None

        if not ES_DISPONIBLE:
            logger.warning(
                "Elasticsearch no esta instalado. Busqueda deshabilitada. "
                "Instalar con: pip install elasticsearch"
            )
            return

        # Configuracion desde variables de entorno o parametros
        hosts = hosts or [
            f"{os.environ.get('ELASTICSEARCH_HOST', 'localhost')}:"
            f"{os.environ.get('ELASTICSEARCH_PORT', '9200')}"
        ]
        username = username or os.environ.get('ELASTICSEARCH_USER')
        password = password or os.environ.get('ELASTICSEARCH_PASSWORD')

        try:
            # Configurar cliente
            config = {
                "hosts": hosts,
                "timeout": timeout,
                "retry_on_timeout": True,
                "max_retries": 3
            }

            if username and password:
                config["basic_auth"] = (username, password)

            if use_ssl:
                config["use_ssl"] = True
                config["verify_certs"] = verify_certs

            self._es = Elasticsearch(**config)

            # Verificar conexion
            if not self._es.ping():
                raise ConnectionError("No se pudo conectar a Elasticsearch")

            info = self._es.info()
            logger.info(
                f"Conectado a Elasticsearch {info['version']['number']} "
                f"en {hosts}"
            )

            # Crear indice si no existe
            self._asegurar_indice()

        except Exception as e:
            logger.error(f"Error conectando a Elasticsearch: {e}")
            self._disponible = False
            self._es = None

    def _asegurar_indice(self):
        """Crea el indice de mensajes si no existe."""
        try:
            if not self._es.indices.exists(index=self.INDICE_MENSAJES):
                self._es.indices.create(
                    index=self.INDICE_MENSAJES,
                    body=self.MAPPING_MENSAJES
                )
                logger.info(f"Indice '{self.INDICE_MENSAJES}' creado")
            else:
                logger.debug(f"Indice '{self.INDICE_MENSAJES}' ya existe")
        except Exception as e:
            logger.error(f"Error creando indice: {e}")

    @property
    def disponible(self) -> bool:
        """Indica si Elasticsearch esta disponible."""
        return self._disponible and self._es is not None

    @property
    def cliente(self) -> Optional[Elasticsearch]:
        """Retorna el cliente Elasticsearch nativo."""
        return self._es

    # ═══════════════════════════════════════════════════════════════════════
    # OPERACIONES DE DOCUMENTO
    # ═══════════════════════════════════════════════════════════════════════

    def indexar(
        self,
        indice: str,
        documento: Dict[str, Any],
        id_documento: Optional[str] = None
    ) -> bool:
        """Indexa un documento."""
        if not self.disponible:
            return False

        try:
            self._es.index(
                index=indice,
                id=id_documento,
                document=documento
            )
            return True
        except Exception as e:
            logger.error(f"Error indexando documento: {e}")
            return False

    def obtener(
        self,
        indice: str,
        id_documento: str
    ) -> Optional[Dict[str, Any]]:
        """Obtiene un documento por ID."""
        if not self.disponible:
            return None

        try:
            result = self._es.get(index=indice, id=id_documento)
            return result["_source"]
        except Exception as e:
            logger.debug(f"Documento no encontrado: {e}")
            return None

    def actualizar(
        self,
        indice: str,
        id_documento: str,
        campos: Dict[str, Any]
    ) -> bool:
        """Actualiza campos de un documento."""
        if not self.disponible:
            return False

        try:
            self._es.update(
                index=indice,
                id=id_documento,
                doc=campos
            )
            return True
        except Exception as e:
            logger.error(f"Error actualizando documento: {e}")
            return False

    def eliminar(
        self,
        indice: str,
        id_documento: str
    ) -> bool:
        """Elimina un documento."""
        if not self.disponible:
            return False

        try:
            self._es.delete(index=indice, id=id_documento)
            return True
        except Exception as e:
            logger.error(f"Error eliminando documento: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # OPERACIONES BULK
    # ═══════════════════════════════════════════════════════════════════════

    def bulk_indexar(
        self,
        indice: str,
        documentos: List[Dict[str, Any]],
        campo_id: str = "id"
    ) -> int:
        """
        Indexa multiples documentos en batch.

        Args:
            indice: Nombre del indice
            documentos: Lista de documentos
            campo_id: Campo a usar como _id

        Returns:
            Numero de documentos indexados
        """
        if not self.disponible or not documentos:
            return 0

        try:
            actions = [
                {
                    "_index": indice,
                    "_id": str(doc.get(campo_id)),
                    "_source": doc
                }
                for doc in documentos
            ]

            success, errors = helpers.bulk(
                self._es,
                actions,
                raise_on_error=False
            )

            if errors:
                logger.warning(f"Errores en bulk: {len(errors)}")

            return success

        except Exception as e:
            logger.error(f"Error en bulk indexar: {e}")
            return 0

    def bulk_eliminar(
        self,
        indice: str,
        ids: List[str]
    ) -> int:
        """Elimina multiples documentos."""
        if not self.disponible or not ids:
            return 0

        try:
            actions = [
                {
                    "_op_type": "delete",
                    "_index": indice,
                    "_id": str(id_doc)
                }
                for id_doc in ids
            ]

            success, _ = helpers.bulk(
                self._es,
                actions,
                raise_on_error=False
            )
            return success

        except Exception as e:
            logger.error(f"Error en bulk eliminar: {e}")
            return 0

    # ═══════════════════════════════════════════════════════════════════════
    # OPERACIONES DE BUSQUEDA
    # ═══════════════════════════════════════════════════════════════════════

    def buscar(
        self,
        indice: str,
        query: Dict[str, Any],
        size: int = 20,
        from_: int = 0,
        sort: Optional[List[Dict]] = None,
        highlight: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta una busqueda.

        Args:
            indice: Nombre del indice
            query: Query DSL de Elasticsearch
            size: Numero de resultados
            from_: Offset para paginacion
            sort: Ordenamiento
            highlight: Configuracion de highlighting

        Returns:
            Respuesta de Elasticsearch
        """
        if not self.disponible:
            return {"hits": {"hits": [], "total": {"value": 0}}}

        try:
            body = {"query": query, "size": size, "from": from_}

            if sort:
                body["sort"] = sort

            if highlight:
                body["highlight"] = highlight

            return self._es.search(index=indice, body=body)

        except Exception as e:
            logger.error(f"Error en busqueda: {e}")
            return {"hits": {"hits": [], "total": {"value": 0}}}

    def contar(
        self,
        indice: str,
        query: Optional[Dict[str, Any]] = None
    ) -> int:
        """Cuenta documentos que coinciden con la query."""
        if not self.disponible:
            return 0

        try:
            if query:
                result = self._es.count(index=indice, query=query)
            else:
                result = self._es.count(index=indice)
            return result["count"]
        except Exception as e:
            logger.error(f"Error contando: {e}")
            return 0

    # ═══════════════════════════════════════════════════════════════════════
    # OPERACIONES DE INDICE
    # ═══════════════════════════════════════════════════════════════════════

    def crear_indice(
        self,
        nombre: str,
        configuracion: Dict[str, Any]
    ) -> bool:
        """Crea un indice."""
        if not self.disponible:
            return False

        try:
            self._es.indices.create(index=nombre, body=configuracion)
            return True
        except Exception as e:
            logger.error(f"Error creando indice: {e}")
            return False

    def existe_indice(self, nombre: str) -> bool:
        """Verifica si un indice existe."""
        if not self.disponible:
            return False

        try:
            return self._es.indices.exists(index=nombre)
        except Exception as e:
            logger.error(f"Error verificando indice: {e}")
            return False

    def eliminar_indice(self, nombre: str) -> bool:
        """Elimina un indice."""
        if not self.disponible:
            return False

        try:
            self._es.indices.delete(index=nombre)
            return True
        except Exception as e:
            logger.error(f"Error eliminando indice: {e}")
            return False

    def refrescar(self, nombre: str) -> bool:
        """Refresca el indice."""
        if not self.disponible:
            return False

        try:
            self._es.indices.refresh(index=nombre)
            return True
        except Exception as e:
            logger.error(f"Error refrescando indice: {e}")
            return False

    def estadisticas(self, nombre: str) -> Dict[str, Any]:
        """Obtiene estadisticas del indice."""
        if not self.disponible:
            return {}

        try:
            stats = self._es.indices.stats(index=nombre)
            return stats["indices"].get(nombre, {})
        except Exception as e:
            logger.error(f"Error obteniendo estadisticas: {e}")
            return {}


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════

def obtener_cliente_elasticsearch(
    hosts: Optional[List[str]] = None
) -> ClienteElasticsearch:
    """
    Obtiene el cliente Elasticsearch singleton.

    Uso:
        es = obtener_cliente_elasticsearch()
        es.buscar(...)
    """
    global _cliente
    if _cliente is None:
        _cliente = ClienteElasticsearch(hosts=hosts)
    return _cliente
