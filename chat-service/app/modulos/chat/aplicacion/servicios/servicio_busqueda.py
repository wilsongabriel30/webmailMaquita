# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SERVICIO DE BUSQUEDA - CHAT                               ║
║               Facade para Operaciones de Busqueda Full-Text                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Proporciona una interfaz unificada para busqueda de mensajes
usando Elasticsearch como backend.

USO:
    from modulos.chat.aplicacion.servicios import ServicioBusqueda

    busqueda = ServicioBusqueda()

    # Buscar en todas las conversaciones
    resultados = busqueda.buscar_global(usuario_id=123, query="reunion")

    # Buscar en una conversacion
    resultados = busqueda.buscar_en_conversacion(
        conversacion_id=456,
        query="proyecto",
        usuario_id=123
    )

    # Busqueda avanzada con filtros
    from modulos.chat.dominio.repositorios import FiltrosBusqueda
    filtros = FiltrosBusqueda(
        query="informe",
        usuario_id=123,
        fecha_desde=datetime(2026, 1, 1),
        solo_con_archivos=True
    )
    resultados = busqueda.buscar(filtros)

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from ...dominio.repositorios.repositorio_busqueda import (
    BuscadorMensajes,
    IndexadorMensajes,
    AdministradorIndice,
    ResultadoBusqueda,
    FiltrosBusqueda,
)
from ...dominio.value_objects.tipos_chat import TipoMensaje
from ...infraestructura.busqueda import (
    BuscadorMensajesElasticsearch,
    IndexadorMensajesElasticsearch,
    AdministradorIndiceElasticsearch,
    obtener_cliente_elasticsearch,
)

logger = logging.getLogger(__name__)


class ServicioBusqueda:
    """
    Servicio unificado de busqueda para el modulo de chat.

    Beneficios:
    - Una sola interfaz para busqueda e indexacion
    - Manejo de errores centralizado
    - Facil de mockear en tests
    - Fallback silencioso si ES no esta disponible
    """

    def __init__(
        self,
        buscador: Optional[BuscadorMensajes] = None,
        indexador: Optional[IndexadorMensajes] = None,
        administrador: Optional[AdministradorIndice] = None
    ):
        """
        Inicializa el servicio de busqueda.

        Args:
            buscador: Buscador personalizado (opcional)
            indexador: Indexador personalizado (opcional)
            administrador: Administrador personalizado (opcional)
        """
        cliente = obtener_cliente_elasticsearch()

        self._buscador = buscador or BuscadorMensajesElasticsearch(cliente)
        self._indexador = indexador or IndexadorMensajesElasticsearch(cliente)
        self._admin = administrador or AdministradorIndiceElasticsearch(cliente)
        self._cliente = cliente

    @property
    def disponible(self) -> bool:
        """Indica si la busqueda esta disponible."""
        return self._cliente.disponible

    # ═══════════════════════════════════════════════════════════════════════
    # BUSQUEDA
    # ═══════════════════════════════════════════════════════════════════════

    def buscar(self, filtros: FiltrosBusqueda) -> ResultadoBusqueda:
        """
        Busqueda avanzada con filtros.

        Args:
            filtros: Criterios de busqueda

        Returns:
            ResultadoBusqueda con mensajes y metadata
        """
        return self._buscador.buscar(filtros)

    def buscar_global(
        self,
        usuario_id: int,
        query: str,
        limite: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Busca en todas las conversaciones del usuario.

        Args:
            usuario_id: ID del usuario
            query: Texto a buscar
            limite: Maximo de resultados

        Returns:
            Lista de mensajes encontrados
        """
        return self._buscador.buscar_global(usuario_id, query, limite)

    def buscar_en_conversacion(
        self,
        conversacion_id: int,
        query: str,
        usuario_id: int,
        limite: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Busca dentro de una conversacion especifica.

        Args:
            conversacion_id: ID de la conversacion
            query: Texto a buscar
            usuario_id: ID del usuario (para permisos)
            limite: Maximo de resultados

        Returns:
            Lista de mensajes encontrados
        """
        return self._buscador.buscar_en_conversacion(
            conversacion_id, query, usuario_id, limite
        )

    def buscar_mensajes(
        self,
        usuario_id: int,
        query: str,
        conversacion_id: Optional[int] = None,
        remitente_id: Optional[int] = None,
        tipo: Optional[TipoMensaje] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        solo_con_archivos: bool = False,
        pagina: int = 1,
        por_pagina: int = 20
    ) -> ResultadoBusqueda:
        """
        Busca mensajes con multiples filtros.

        Metodo de conveniencia que crea FiltrosBusqueda internamente.
        """
        filtros = FiltrosBusqueda(
            query=query,
            usuario_id=usuario_id,
            conversacion_id=conversacion_id,
            remitente_id=remitente_id,
            tipo_mensaje=tipo,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            solo_con_archivos=solo_con_archivos,
            pagina=pagina,
            por_pagina=por_pagina
        )
        return self.buscar(filtros)

    def sugerir(
        self,
        usuario_id: int,
        prefijo: str,
        limite: int = 10
    ) -> List[str]:
        """
        Sugiere terminos de busqueda.

        Args:
            usuario_id: ID del usuario
            prefijo: Inicio del termino
            limite: Maximo de sugerencias

        Returns:
            Lista de sugerencias
        """
        return self._buscador.sugerir(usuario_id, prefijo, limite)

    # ═══════════════════════════════════════════════════════════════════════
    # INDEXACION
    # ═══════════════════════════════════════════════════════════════════════

    def indexar_mensaje(self, mensaje: Dict[str, Any]) -> bool:
        """
        Indexa un mensaje nuevo.

        Llamar despues de crear un mensaje en la BD.
        """
        return self._indexador.indexar(mensaje)

    def indexar_mensajes(self, mensajes: List[Dict[str, Any]]) -> int:
        """
        Indexa multiples mensajes en batch.

        Util para migracion inicial.
        """
        return self._indexador.indexar_lote(mensajes)

    def actualizar_mensaje(
        self,
        mensaje_id: int,
        contenido: str,
        editado_en: Optional[datetime] = None
    ) -> bool:
        """
        Actualiza un mensaje en el indice.

        Llamar despues de editar un mensaje.
        """
        campos = {"contenido": contenido}
        if editado_en:
            campos["editado_en"] = editado_en.isoformat()
        return self._indexador.actualizar(mensaje_id, campos)

    def eliminar_mensaje(self, mensaje_id: int) -> bool:
        """
        Elimina un mensaje del indice.

        Llamar despues de eliminar un mensaje.
        """
        return self._indexador.eliminar(mensaje_id)

    def marcar_mensaje_eliminado(self, mensaje_id: int) -> bool:
        """
        Marca un mensaje como eliminado (soft delete).

        Mantiene el mensaje en el indice pero no aparece en busquedas.
        """
        return self._indexador.actualizar(mensaje_id, {"activo": False})

    def reindexar_conversacion(
        self,
        conversacion_id: int,
        mensajes: List[Dict[str, Any]]
    ) -> int:
        """
        Reindexa todos los mensajes de una conversacion.

        Util si hay problemas de sincronizacion.
        """
        return self._indexador.reindexar_conversacion(conversacion_id, mensajes)

    # ═══════════════════════════════════════════════════════════════════════
    # ADMINISTRACION
    # ═══════════════════════════════════════════════════════════════════════

    def inicializar_indice(self) -> bool:
        """
        Crea el indice de mensajes si no existe.

        Llamar al iniciar la aplicacion.
        """
        return self._admin.crear_indice_mensajes()

    def recrear_indice(self) -> bool:
        """
        Elimina y recrea el indice de mensajes.

        PELIGROSO: Elimina todos los datos indexados.
        """
        return self._admin.recrear_indice_mensajes()

    def refrescar_indice(self) -> bool:
        """
        Hace que los documentos recientes sean buscables.

        ES lo hace automaticamente cada segundo, pero puede forzarse.
        """
        return self._admin.refrescar(self._cliente.INDICE_MENSAJES)

    def optimizar_indice(self) -> bool:
        """
        Optimiza el indice (merge segments).

        Ejecutar en horarios de baja carga.
        """
        return self._admin.optimizar(self._cliente.INDICE_MENSAJES)

    def obtener_estadisticas(self) -> Dict[str, Any]:
        """
        Obtiene estadisticas del indice.
        """
        if not self.disponible:
            return {"disponible": False}

        stats = self._admin.obtener_estadisticas(self._cliente.INDICE_MENSAJES)
        salud = self._admin.obtener_estado_salud()

        return {
            "disponible": True,
            "indice": stats,
            "cluster": salud
        }

    # ═══════════════════════════════════════════════════════════════════════
    # OPERACIONES COMPUESTAS
    # ═══════════════════════════════════════════════════════════════════════

    def al_crear_mensaje(
        self,
        mensaje: Dict[str, Any],
        participantes_ids: List[int]
    ) -> bool:
        """
        Hook para cuando se crea un mensaje.

        Agrega los participantes al documento e indexa.
        """
        mensaje_con_participantes = {
            **mensaje,
            "participantes": participantes_ids
        }
        return self.indexar_mensaje(mensaje_con_participantes)

    def al_editar_mensaje(
        self,
        mensaje_id: int,
        nuevo_contenido: str
    ) -> bool:
        """
        Hook para cuando se edita un mensaje.
        """
        return self.actualizar_mensaje(
            mensaje_id,
            nuevo_contenido,
            datetime.now()
        )

    def al_eliminar_mensaje(
        self,
        mensaje_id: int,
        eliminacion_fisica: bool = False
    ) -> bool:
        """
        Hook para cuando se elimina un mensaje.

        Args:
            mensaje_id: ID del mensaje
            eliminacion_fisica: True para eliminar del indice,
                               False para marcar como eliminado
        """
        if eliminacion_fisica:
            return self.eliminar_mensaje(mensaje_id)
        return self.marcar_mensaje_eliminado(mensaje_id)

    def migrar_mensajes_existentes(
        self,
        obtener_mensajes_func,
        batch_size: int = 1000
    ) -> Dict[str, int]:
        """
        Migra mensajes existentes de la BD al indice.

        Args:
            obtener_mensajes_func: Funcion que retorna mensajes por batch
            batch_size: Tamaño del batch

        Returns:
            {"total": N, "indexados": M, "errores": E}
        """
        total = 0
        indexados = 0
        offset = 0

        while True:
            mensajes = obtener_mensajes_func(offset=offset, limite=batch_size)

            if not mensajes:
                break

            total += len(mensajes)
            indexados += self.indexar_mensajes(mensajes)
            offset += batch_size

            logger.info(f"Migrados {indexados}/{total} mensajes")

        return {
            "total": total,
            "indexados": indexados,
            "errores": total - indexados
        }
