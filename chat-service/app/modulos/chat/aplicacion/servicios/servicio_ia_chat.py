# -*- coding: utf-8 -*-
"""
Servicio de Aplicacion: IA Chat

Orquesta las operaciones de chat con IA Maquita.
Coordina las entidades de dominio con el AI Worker.

CAPA: modulos/chat/aplicacion/servicios
ARQUITECTURA: Hexagonal - 100%

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-06
"""

import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from dataclasses import dataclass
from uuid import uuid4

from ...dominio.entidades.conversacion_ia import (
    ConversacionIA,
    MensajeIA,
    ConfiguracionIAUsuario,
    IA_MAQUITA_USER_ID
)
from ...dominio.value_objects.tipos_chat import (
    TipoConversacion,
    TipoMensaje,
    CapacidadIA,
    EstadoIA,
    ConstantesChat
)

# Importar servicio de Ollama desde compartido
from compartido.servicios.ai_worker_service import OllamaService, ChatResponse

# Importar servicios de conocimiento y busqueda web
try:
    from compartido.servicios.knowledge_service import (
        KnowledgeService,
        obtener_servicio_conocimiento,
        obtener_contexto_para_pregunta
    )
    KNOWLEDGE_AVAILABLE = True
except ImportError:
    KNOWLEDGE_AVAILABLE = False

try:
    from compartido.servicios.web_search_service import (
        WebSearchService,
        obtener_servicio_busqueda,
        buscar_en_web
    )
    WEB_SEARCH_AVAILABLE = True
except ImportError:
    WEB_SEARCH_AVAILABLE = False

# Importar servicio de busqueda mejorada v3.0
try:
    from compartido.servicios.busqueda_ia_mejorada import (
        BusquedaIAMejorada,
        ResultadoBusquedaMejorado,
        obtener_servicio_busqueda_mejorada,
        buscar_web_mejorado
    )
    BUSQUEDA_MEJORADA_AVAILABLE = True
except ImportError:
    BUSQUEDA_MEJORADA_AVAILABLE = False


logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURACION DE MODELO POR DEFECTO
# =============================================================================

MODELO_IA_DEFECTO = "qwen2.5:7b"  # Modelo base mientras se corrige maquita:production


# =============================================================================
# SISTEMA PROMPT PARA IA MAQUITA
# =============================================================================

SISTEMA_IA_MAQUITA = """Eres IA Maquita, el asistente virtual inteligente de Fundación Maquita Cushunchic.

## DATOS CRITICOS QUE NUNCA DEBES OLVIDAR:
- Maquita Cushunchic es una organizacion ECUATORIANA (NO peruana, NO de otro pais)
- Fue fundada en 1985 en Quito, ECUADOR
- Fundador: Padre Graziano Mason (sacerdote italiano que llego a Ecuador)
- Sede principal: Quito, Ecuador
- "Maquita Cushunchic" significa "Demos la mano" en quichua
- Redes oficiales: facebook.com/MaquitaCushunchic, @maquitacushunchic
- PROPÓSITO DE MAQUITA: "Generar Cambios Sostenibles que mejoran vidas"

## Tu personalidad:
- Amable, profesional y servicial
- Conoces la cultura y valores de Maquita (comercio justo, economia solidaria)
- Respondes en español de manera clara y concisa
- Ayudas con consultas sobre procesos, informacion y tareas del sistema

## Capacidades:
- Responder preguntas sobre Maquita usando el conocimiento institucional
- Buscar informacion en internet cuando sea necesario
- Asistir con tareas administrativas
- Explicar procedimientos y politicas
- Resumir documentos y transcripciones
- Aprender de conversaciones anteriores para mejorar respuestas

## Cuando recibas contexto adicional:
- PRIORIDAD MAXIMA: "CONOCIMIENTO INSTITUCIONAL" - SIEMPRE usalo primero
- Si te proporcionan "DOCUMENTOS RELEVANTES", cita la fuente al responder
- "INFORMACION DE INTERNET" solo usarla si NO contradice el conocimiento institucional
- Si te proporcionan "PREGUNTAS SIMILARES ANTERIORES", usalas como referencia

## LIMITACIONES CRITICAS:
- NUNCA inventar informacion sobre Maquita que no este en el contexto
- NUNCA decir que Maquita es de Peru u otro pais - ES DE ECUADOR
- Si no tienes informacion suficiente, di "No tengo esa informacion en mi base de conocimiento"
- Para temas oficiales, recomendar consultar con el area correspondiente
- Si la web contradice el conocimiento institucional, PRIORIZA el conocimiento institucional

## Formato de respuestas:
- Usa parrafos cortos y faciles de leer
- Si hay pasos, enumeralos
- Se directo y evita rodeos innecesarios
- Si usaste informacion de internet, menciona que buscaste en la web"""


# =============================================================================
# DTOs DE RESPUESTA
# =============================================================================

@dataclass
class RespuestaIAChat:
    """Respuesta generica del servicio de IA Chat."""
    exito: bool
    mensaje: str
    datos: Optional[Dict[str, Any]] = None


@dataclass
class MensajeIADTO:
    """DTO para mensaje de IA con soporte multimedia v3.0."""
    id: Optional[int]
    public_id: str
    es_usuario: bool
    contenido: str
    tipo: str
    creado_en: str
    ia_metadata: Optional[Dict[str, Any]] = None
    # V3.0: Campos multimedia de busqueda
    imagenes: List[Dict[str, Any]] = None
    videos: List[Dict[str, Any]] = None
    fuentes: List[Dict[str, Any]] = None
    busqueda_realizada: bool = False
    intencion_detectada: str = None

    @classmethod
    def desde_entidad(cls, msg: MensajeIA) -> 'MensajeIADTO':
        data = msg.to_dict()
        return cls(
            id=data['id'],
            public_id=data['public_id'],
            es_usuario=data['es_usuario'],
            contenido=data['contenido'],
            tipo=data['tipo'],
            creado_en=data['creado_en'],
            ia_metadata=data.get('ia_metadata'),
            # V3.0: Multimedia (se carga desde BD o se asigna despues)
            imagenes=data.get('imagenes', []),
            videos=data.get('videos', []),
            fuentes=data.get('fuentes', []),
            busqueda_realizada=data.get('busqueda_realizada', False),
            intencion_detectada=data.get('intencion_detectada')
        )


@dataclass
class ConversacionIADTO:
    """DTO para conversacion IA."""
    id: int
    public_id: str
    titulo: str
    total_mensajes: int
    ultimo_mensaje_en: Optional[str]
    creada_en: str
    estado: str = 'activa'
    mensajes: List[MensajeIADTO] = None

    @classmethod
    def desde_entidad(cls, conv: ConversacionIA, incluir_mensajes: bool = False) -> 'ConversacionIADTO':
        # Determinar estado basado en flags
        if conv.archivada:
            estado = 'archivada'
        elif not conv.activa:
            estado = 'eliminada'
        else:
            estado = 'activa'

        dto = cls(
            id=conv.id,
            public_id=str(conv.public_id),
            titulo=conv.titulo,
            total_mensajes=conv.total_mensajes,
            ultimo_mensaje_en=conv.ultimo_mensaje_en.isoformat() if conv.ultimo_mensaje_en else None,
            creada_en=conv.creada_en.isoformat() if conv.creada_en else None,
            estado=estado
        )
        if incluir_mensajes:
            dto.mensajes = [MensajeIADTO.desde_entidad(m) for m in conv.mensajes]
        return dto


# =============================================================================
# ALMACENAMIENTO EN MEMORIA (Temporal - luego migrar a PostgreSQL)
# =============================================================================

class AlmacenamientoIAMemoria:
    """
    Almacenamiento temporal en memoria para conversaciones IA.
    TODO: Migrar a repositorio PostgreSQL.
    """

    def __init__(self):
        self._conversaciones: Dict[int, ConversacionIA] = {}
        self._conversaciones_por_usuario: Dict[int, List[int]] = {}
        self._configuraciones: Dict[int, ConfiguracionIAUsuario] = {}
        self._next_conv_id = 1
        self._next_msg_id = 1

    def crear_conversacion(self, usuario_id: int, titulo: str = None) -> ConversacionIA:
        """Crea una nueva conversacion."""
        conv = ConversacionIA.crear_nueva(usuario_id, titulo)
        conv.id = self._next_conv_id
        self._next_conv_id += 1

        self._conversaciones[conv.id] = conv

        if usuario_id not in self._conversaciones_por_usuario:
            self._conversaciones_por_usuario[usuario_id] = []
        self._conversaciones_por_usuario[usuario_id].append(conv.id)

        return conv

    def obtener_conversacion(self, conv_id: int) -> Optional[ConversacionIA]:
        """Obtiene una conversacion por ID."""
        return self._conversaciones.get(conv_id)

    def obtener_conversacion_por_public_id(self, public_id: str) -> Optional[ConversacionIA]:
        """Obtiene una conversacion por public_id."""
        for conv in self._conversaciones.values():
            if str(conv.public_id) == public_id:
                return conv
        return None

    def obtener_conversaciones_usuario(self, usuario_id: int, incluir_archivadas: bool = False) -> List[ConversacionIA]:
        """Obtiene todas las conversaciones de un usuario."""
        conv_ids = self._conversaciones_por_usuario.get(usuario_id, [])
        conversaciones = []
        for conv_id in conv_ids:
            conv = self._conversaciones.get(conv_id)
            if conv:
                if incluir_archivadas or not conv.archivada:
                    conversaciones.append(conv)

        # Ordenar por ultimo mensaje (mas reciente primero)
        conversaciones.sort(key=lambda c: c.ultimo_mensaje_en or c.creada_en, reverse=True)
        return conversaciones

    def agregar_mensaje(self, conv_id: int, mensaje: MensajeIA) -> MensajeIA:
        """Agrega un mensaje a una conversacion."""
        mensaje.id = self._next_msg_id
        self._next_msg_id += 1
        mensaje.conversacion_ia_id = conv_id

        conv = self._conversaciones.get(conv_id)
        if conv:
            conv.mensajes.append(mensaje)
            conv.total_mensajes += 1
            conv.ultimo_mensaje_en = datetime.now()
            conv.actualizada_en = datetime.now()

        return mensaje

    def obtener_configuracion(self, usuario_id: int) -> ConfiguracionIAUsuario:
        """Obtiene o crea configuracion de usuario."""
        if usuario_id not in self._configuraciones:
            self._configuraciones[usuario_id] = ConfiguracionIAUsuario(
                id=usuario_id,
                usuario_id=usuario_id,
                creado_en=datetime.now()
            )
        return self._configuraciones[usuario_id]

    def actualizar_configuracion(self, config: ConfiguracionIAUsuario):
        """Actualiza configuracion de usuario."""
        self._configuraciones[config.usuario_id] = config

    def eliminar_conversacion(self, conv_id: int) -> bool:
        """Elimina una conversacion."""
        conv = self._conversaciones.get(conv_id)
        if conv:
            del self._conversaciones[conv_id]
            if conv.usuario_id in self._conversaciones_por_usuario:
                self._conversaciones_por_usuario[conv.usuario_id].remove(conv_id)
            return True
        return False


# =============================================================================
# ALMACENAMIENTO EN POSTGRESQL (Persistente)
# =============================================================================

class AlmacenamientoIAPostgres:
    """
    Almacenamiento persistente en PostgreSQL para conversaciones IA.
    Usa la base de datos ia_maquita.
    """

    def __init__(self):
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        from config import Config

        self.engine = create_engine(
            Config.IA_MAQUITA_DATABASE_URI,
            pool_size=2,
            pool_recycle=1800,
            pool_pre_ping=True
        )
        self.Session = sessionmaker(bind=self.engine)
        self._cache_config: Dict[int, ConfiguracionIAUsuario] = {}
        logger.info("AlmacenamientoIAPostgres inicializado con BD ia_maquita")

    def _get_session(self):
        """Obtiene una sesion de base de datos."""
        return self.Session()

    def crear_conversacion(self, usuario_id: int, titulo: str = None) -> ConversacionIA:
        """Crea una nueva conversacion en la BD."""
        from sqlalchemy import text

        conv = ConversacionIA.crear_nueva(usuario_id, titulo)
        session = self._get_session()

        try:
            result = session.execute(
                text("""
                    INSERT INTO conversaciones_ia
                    (usuario_id, titulo, modelo_preferido, created_at, updated_at)
                    VALUES (:usuario_id, :titulo, :modelo, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    RETURNING id
                """),
                {
                    'usuario_id': usuario_id,
                    'titulo': conv.titulo,
                    'modelo': conv.modelo_preferido
                }
            )
            conv.id = result.fetchone()[0]
            session.commit()
            logger.info(f"Conversacion IA creada en BD: id={conv.id}, usuario={usuario_id}")
            return conv

        except Exception as e:
            session.rollback()
            logger.error(f"Error creando conversacion en BD: {e}")
            raise
        finally:
            session.close()

    def obtener_conversacion(self, conv_id: int, incluir_no_activas: bool = False) -> Optional[ConversacionIA]:
        """Obtiene una conversacion por ID."""
        from sqlalchemy import text

        session = self._get_session()
        try:
            # Obtener conversacion - con o sin filtro de estado
            if incluir_no_activas:
                query = """
                    SELECT id, usuario_id, titulo, resumen, tipo, estado,
                           total_mensajes, modelo_preferido, created_at, updated_at,
                           ultimo_mensaje_at, metadata
                    FROM conversaciones_ia
                    WHERE id = :id AND estado != 'eliminada'
                """
            else:
                query = """
                    SELECT id, usuario_id, titulo, resumen, tipo, estado,
                           total_mensajes, modelo_preferido, created_at, updated_at,
                           ultimo_mensaje_at, metadata
                    FROM conversaciones_ia
                    WHERE id = :id AND estado = 'activa'
                """
            result = session.execute(text(query), {'id': conv_id})
            row = result.fetchone()

            if not row:
                return None

            conv = ConversacionIA(
                id=row[0],
                public_id=uuid4(),  # Generar nuevo si no existe
                usuario_id=row[1],
                titulo=row[2],
                activa=row[4] != 'eliminada',
                archivada=row[4] == 'archivada',
                modelo_preferido=row[7] or 'llama3.2:3b',
                total_mensajes=row[6] or 0,
                creada_en=row[8],
                actualizada_en=row[9],
                ultimo_mensaje_en=row[10],
                mensajes=[]
            )

            # Cargar mensajes
            mensajes_result = session.execute(
                text("""
                    SELECT id, rol, contenido, modelo_usado, tokens_prompt,
                           tokens_respuesta, tiempo_respuesta_ms, capacidad, created_at
                    FROM mensajes_ia
                    WHERE conversacion_id = :conv_id
                    ORDER BY created_at ASC
                """),
                {'conv_id': conv_id}
            )

            for msg_row in mensajes_result:
                es_usuario = msg_row[1] == 'user'
                tipo = TipoMensaje.TEXTO if es_usuario else TipoMensaje.IA_RESPUESTA

                mensaje = MensajeIA(
                    id=msg_row[0],
                    public_id=uuid4(),
                    conversacion_ia_id=conv_id,
                    es_usuario=es_usuario,
                    contenido=msg_row[2],
                    tipo=tipo,
                    modelo=msg_row[3],
                    tokens_prompt=msg_row[4],
                    tokens_respuesta=msg_row[5],
                    tiempo_respuesta_ms=msg_row[6],
                    capacidad_usada=CapacidadIA(msg_row[7]) if msg_row[7] else CapacidadIA.CHAT,
                    creado_en=msg_row[8]
                )
                conv.mensajes.append(mensaje)

            return conv

        except Exception as e:
            logger.error(f"Error obteniendo conversacion {conv_id}: {e}")
            return None
        finally:
            session.close()

    def obtener_conversacion_por_public_id(self, public_id: str) -> Optional[ConversacionIA]:
        """No soportado directamente - usar ID numerico."""
        # En esta implementacion usamos IDs numericos
        return None

    def obtener_conversaciones_usuario(self, usuario_id: int, incluir_archivadas: bool = False) -> List[ConversacionIA]:
        """Obtiene todas las conversaciones de un usuario."""
        from sqlalchemy import text

        session = self._get_session()
        try:
            query = """
                SELECT id, titulo, total_mensajes, modelo_preferido,
                       created_at, updated_at, ultimo_mensaje_at, estado
                FROM conversaciones_ia
                WHERE usuario_id = :usuario_id
            """

            if not incluir_archivadas:
                query += " AND estado = 'activa'"
            else:
                query += " AND estado != 'eliminada'"

            query += " ORDER BY COALESCE(ultimo_mensaje_at, created_at) DESC"

            result = session.execute(text(query), {'usuario_id': usuario_id})

            conversaciones = []
            for row in result:
                conv = ConversacionIA(
                    id=row[0],
                    public_id=uuid4(),
                    usuario_id=usuario_id,
                    titulo=row[1],
                    total_mensajes=row[2] or 0,
                    modelo_preferido=row[3] or 'llama3.2:3b',
                    creada_en=row[4],
                    actualizada_en=row[5],
                    ultimo_mensaje_en=row[6],
                    archivada=row[7] == 'archivada',
                    mensajes=[]
                )
                conversaciones.append(conv)

            return conversaciones

        except Exception as e:
            logger.error(f"Error obteniendo conversaciones de usuario {usuario_id}: {e}")
            return []
        finally:
            session.close()

    def agregar_mensaje(
        self,
        conv_id: int,
        mensaje: MensajeIA,
        imagenes: list = None,
        videos: list = None,
        fuentes: list = None,
        busqueda_realizada: bool = False,
        intencion_detectada: str = None
    ) -> MensajeIA:
        """
        Agrega un mensaje a una conversacion.

        Args:
            conv_id: ID de la conversacion
            mensaje: Mensaje a agregar
            imagenes: Lista de imagenes de busqueda (v3.0)
            videos: Lista de videos de busqueda (v3.0)
            fuentes: Lista de fuentes consultadas (v3.0)
            busqueda_realizada: Si se realizo busqueda web (v3.0)
            intencion_detectada: Intencion detectada del mensaje (v3.0)
        """
        import json
        from sqlalchemy import text

        session = self._get_session()
        try:
            rol = 'user' if mensaje.es_usuario else 'assistant'
            capacidad = mensaje.capacidad_usada.value if mensaje.capacidad_usada else 'chat'

            # Serializar listas a JSON para campos JSONB
            imagenes_json = json.dumps(imagenes or [])
            videos_json = json.dumps(videos or [])
            fuentes_json = json.dumps(fuentes or [])

            result = session.execute(
                text("""
                    INSERT INTO mensajes_ia
                    (conversacion_id, rol, contenido, modelo_usado, tokens_prompt,
                     tokens_respuesta, tiempo_respuesta_ms, capacidad,
                     imagenes, videos, fuentes, busqueda_realizada, intencion_detectada,
                     created_at)
                    VALUES (:conv_id, :rol, :contenido, :modelo, :tokens_prompt,
                            :tokens_respuesta, :tiempo_ms, :capacidad,
                            :imagenes, :videos, :fuentes,
                            :busqueda, :intencion,
                            CURRENT_TIMESTAMP)
                    RETURNING id
                """),
                {
                    'conv_id': conv_id,
                    'rol': rol,
                    'contenido': mensaje.contenido,
                    'modelo': mensaje.modelo,
                    'tokens_prompt': mensaje.tokens_prompt or 0,
                    'tokens_respuesta': mensaje.tokens_respuesta or 0,
                    'tiempo_ms': mensaje.tiempo_respuesta_ms or 0,
                    'capacidad': capacidad,
                    'imagenes': imagenes_json,
                    'videos': videos_json,
                    'fuentes': fuentes_json,
                    'busqueda': busqueda_realizada,
                    'intencion': intencion_detectada
                }
            )
            mensaje.id = result.fetchone()[0]
            mensaje.conversacion_ia_id = conv_id

            session.commit()
            logger.debug(f"Mensaje agregado: conv={conv_id}, id={mensaje.id}, rol={rol}, busqueda={busqueda_realizada}")
            return mensaje

        except Exception as e:
            session.rollback()
            logger.error(f"Error agregando mensaje a conv {conv_id}: {e}")
            raise
        finally:
            session.close()

    def obtener_configuracion(self, usuario_id: int) -> ConfiguracionIAUsuario:
        """Obtiene o crea configuracion de usuario."""
        from sqlalchemy import text

        # Cache local para evitar consultas repetidas
        if usuario_id in self._cache_config:
            config = self._cache_config[usuario_id]
            # Verificar reset diario
            if config.ultimo_reset and config.ultimo_reset.date() < datetime.now().date():
                config.reset_diario()
            return config

        session = self._get_session()
        try:
            result = session.execute(
                text("""
                    SELECT usuario_id, modelo_preferido, temperatura, max_tokens,
                           mensajes_dia_limite, mensajes_dia_usados, fecha_reset_limite,
                           mostrar_tiempo_respuesta, guardar_historial
                    FROM configuracion_usuario_ia
                    WHERE usuario_id = :usuario_id
                """),
                {'usuario_id': usuario_id}
            )
            row = result.fetchone()

            if row:
                config = ConfiguracionIAUsuario(
                    id=usuario_id,
                    usuario_id=row[0],
                    modelo_preferido=row[1] or 'llama3.2:3b',
                    temperatura=float(row[2]) if row[2] else 0.7,
                    max_tokens_por_respuesta=row[3] or 2048,
                    max_mensajes_por_dia=row[4] or 100,
                    mensajes_hoy=row[5] or 0,
                    ultimo_reset=datetime.combine(row[6], datetime.min.time()) if row[6] else None,
                    creado_en=datetime.now()
                )
            else:
                # Crear configuracion por defecto
                session.execute(
                    text("""
                        INSERT INTO configuracion_usuario_ia (usuario_id)
                        VALUES (:usuario_id)
                        ON CONFLICT (usuario_id) DO NOTHING
                    """),
                    {'usuario_id': usuario_id}
                )
                session.commit()

                config = ConfiguracionIAUsuario(
                    id=usuario_id,
                    usuario_id=usuario_id,
                    creado_en=datetime.now()
                )

            self._cache_config[usuario_id] = config
            return config

        except Exception as e:
            logger.error(f"Error obteniendo configuracion usuario {usuario_id}: {e}")
            return ConfiguracionIAUsuario(
                id=usuario_id,
                usuario_id=usuario_id,
                creado_en=datetime.now()
            )
        finally:
            session.close()

    def actualizar_configuracion(self, config: ConfiguracionIAUsuario):
        """Actualiza configuracion de usuario."""
        from sqlalchemy import text

        session = self._get_session()
        try:
            session.execute(
                text("""
                    UPDATE configuracion_usuario_ia
                    SET modelo_preferido = :modelo,
                        temperatura = :temp,
                        mensajes_dia_usados = :mensajes,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE usuario_id = :usuario_id
                """),
                {
                    'usuario_id': config.usuario_id,
                    'modelo': config.modelo_preferido,
                    'temp': config.temperatura,
                    'mensajes': config.mensajes_hoy
                }
            )
            session.commit()
            self._cache_config[config.usuario_id] = config

        except Exception as e:
            session.rollback()
            logger.error(f"Error actualizando configuracion: {e}")
        finally:
            session.close()

    def archivar_conversacion(self, conv_id: int, archivar: bool = True) -> bool:
        """Archiva o desarchiva una conversacion en la BD."""
        from sqlalchemy import text

        session = self._get_session()
        try:
            nuevo_estado = 'archivada' if archivar else 'activa'
            session.execute(
                text("""
                    UPDATE conversaciones_ia
                    SET estado = :estado, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                """),
                {'id': conv_id, 'estado': nuevo_estado}
            )
            session.commit()
            logger.info(f"Conversacion {conv_id} estado cambiado a: {nuevo_estado}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Error archivando conversacion {conv_id}: {e}")
            return False
        finally:
            session.close()

    def eliminar_conversacion(self, conv_id: int) -> bool:
        """Elimina (marca como eliminada) una conversacion."""
        from sqlalchemy import text

        session = self._get_session()
        try:
            session.execute(
                text("""
                    UPDATE conversaciones_ia
                    SET estado = 'eliminada', updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                """),
                {'id': conv_id}
            )
            session.commit()
            logger.info(f"Conversacion {conv_id} marcada como eliminada")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Error eliminando conversacion {conv_id}: {e}")
            return False
        finally:
            session.close()

    def obtener_conversacion_cualquier_estado(self, conv_id: int) -> Optional[ConversacionIA]:
        """Obtiene una conversacion por ID sin filtrar por estado (para eliminacion permanente)."""
        from sqlalchemy import text

        session = self._get_session()
        try:
            result = session.execute(
                text("""
                    SELECT id, usuario_id, titulo, estado
                    FROM conversaciones_ia
                    WHERE id = :id
                """),
                {'id': conv_id}
            )
            row = result.fetchone()

            if not row:
                return None

            conv = ConversacionIA(
                id=row[0],
                public_id=uuid4(),
                usuario_id=row[1],
                titulo=row[2],
                activa=row[3] != 'eliminada',
                archivada=row[3] == 'archivada',
                mensajes=[]
            )
            return conv

        except Exception as e:
            logger.error(f"Error obteniendo conversacion {conv_id}: {e}")
            return None
        finally:
            session.close()

    def eliminar_conversacion_permanente(self, conv_id: int) -> bool:
        """Elimina PERMANENTEMENTE una conversacion y todos sus mensajes."""
        from sqlalchemy import text

        session = self._get_session()
        try:
            # Primero eliminar mensajes
            session.execute(
                text("DELETE FROM mensajes_ia WHERE conversacion_id = :id"),
                {'id': conv_id}
            )

            # Luego eliminar conversacion
            result = session.execute(
                text("DELETE FROM conversaciones_ia WHERE id = :id"),
                {'id': conv_id}
            )
            session.commit()

            if result.rowcount > 0:
                logger.info(f"Conversacion {conv_id} ELIMINADA PERMANENTEMENTE")
                return True
            return False

        except Exception as e:
            session.rollback()
            logger.error(f"Error eliminando permanentemente conversacion {conv_id}: {e}")
            return False
        finally:
            session.close()


# Funcion para obtener el almacenamiento apropiado
def _obtener_almacenamiento():
    """Obtiene el almacenamiento (PostgreSQL si disponible, memoria como fallback)."""
    from sqlalchemy import text

    try:
        almacenamiento = AlmacenamientoIAPostgres()
        # Verificar conexion
        session = almacenamiento._get_session()
        session.execute(text("SELECT 1"))
        session.close()
        logger.info("Usando almacenamiento PostgreSQL para IA Chat")
        return almacenamiento
    except Exception as e:
        logger.warning(f"No se pudo conectar a BD ia_maquita, usando memoria: {e}")
        return AlmacenamientoIAMemoria()


# Instancia global (singleton) - PostgreSQL con fallback a memoria
_almacenamiento_ia = None


# =============================================================================
# SERVICIO PRINCIPAL DE IA CHAT
# =============================================================================

class ServicioIAChat:
    """
    Servicio de aplicacion para chat con IA Maquita.

    Responsabilidades:
    - Gestionar conversaciones con IA
    - Procesar mensajes de usuario
    - Obtener respuestas de Ollama
    - Mantener historial de contexto

    Uso:
        servicio = ServicioIAChat()

        # Iniciar nueva conversacion
        conv = servicio.crear_conversacion(usuario_id=123)

        # Enviar mensaje
        respuesta = servicio.enviar_mensaje(
            conversacion_id=conv.id,
            usuario_id=123,
            contenido="Hola, necesito ayuda"
        )
        print(respuesta.datos['respuesta_ia'])
    """

    def __init__(self, almacenamiento: AlmacenamientoIAMemoria = None):
        self.almacenamiento = almacenamiento or _almacenamiento_ia
        self.ollama = OllamaService()
        self._estado_ia = EstadoIA.DISPONIBLE

    # =========================================================================
    # ESTADO DE IA
    # =========================================================================

    def verificar_estado(self) -> Dict[str, Any]:
        """Verifica el estado del servicio de IA."""
        health = self.ollama.health()

        if health.healthy:
            self._estado_ia = EstadoIA.DISPONIBLE
        else:
            self._estado_ia = EstadoIA.DESCONECTADO

        # Obtener modelos disponibles
        modelos = []
        try:
            if hasattr(health, 'details') and health.details:
                modelos_raw = health.details.get('models', [])
                # Si es una lista de diccionarios (respuesta de Ollama API)
                if isinstance(modelos_raw, list) and modelos_raw and isinstance(modelos_raw[0], dict):
                    modelos = [m.get('name', str(m)) for m in modelos_raw]
                else:
                    modelos = list(map(str, modelos_raw))
        except Exception as e:
            logger.warning(f"Error obteniendo modelos: {e}")
            modelos = []

        return {
            'estado': self._estado_ia.value,
            'disponible': health.healthy,
            'tiempo_respuesta': health.response_time,
            'modelos_disponibles': modelos,
            'error': health.error,
            'ia_info': {
                'nombre': ConstantesChat.IA_MAQUITA_NOMBRE,
                'avatar': ConstantesChat.IA_MAQUITA_AVATAR,
                'modelo': ConstantesChat.IA_MAQUITA_MODELO,
            }
        }

    def obtener_contacto_ia(self) -> Dict[str, Any]:
        """
        Obtiene los datos de IA Maquita como contacto para mostrar en lista.
        """
        estado = self.verificar_estado()
        return {
            'usuario_id': IA_MAQUITA_USER_ID,
            'nombre': ConstantesChat.IA_MAQUITA_NOMBRE,
            'avatar': ConstantesChat.IA_MAQUITA_AVATAR,
            'es_ia': True,
            'estado': estado['estado'],
            'disponible': estado['disponible'],
            'descripcion': 'Asistente virtual de Maquita',
        }

    # =========================================================================
    # GESTION DE CONVERSACIONES
    # =========================================================================

    def crear_conversacion(
        self,
        usuario_id: int,
        titulo: str = None
    ) -> RespuestaIAChat:
        """
        Crea una nueva conversacion con IA Maquita.
        """
        try:
            conv = self.almacenamiento.crear_conversacion(usuario_id, titulo)
            logger.info(f"Nueva conversacion IA creada: {conv.id} para usuario {usuario_id}")

            return RespuestaIAChat(
                exito=True,
                mensaje="Conversacion creada exitosamente",
                datos={
                    'conversacion': ConversacionIADTO.desde_entidad(conv).__dict__,
                    'ia_contacto': self.obtener_contacto_ia()
                }
            )
        except Exception as e:
            logger.error(f"Error creando conversacion IA: {e}")
            return RespuestaIAChat(
                exito=False,
                mensaje=f"Error al crear conversacion: {str(e)}"
            )

    def obtener_conversacion(
        self,
        conversacion_id: int,
        usuario_id: int,
        incluir_mensajes: bool = True
    ) -> RespuestaIAChat:
        """
        Obtiene una conversacion por ID.
        """
        try:
            conv = self.almacenamiento.obtener_conversacion(conversacion_id)

            if not conv:
                return RespuestaIAChat(
                    exito=False,
                    mensaje="Conversacion no encontrada"
                )

            if conv.usuario_id != usuario_id:
                return RespuestaIAChat(
                    exito=False,
                    mensaje="No tienes acceso a esta conversacion"
                )

            return RespuestaIAChat(
                exito=True,
                mensaje="Conversacion obtenida",
                datos={
                    'conversacion': ConversacionIADTO.desde_entidad(conv, incluir_mensajes).__dict__
                }
            )
        except Exception as e:
            logger.error(f"Error obteniendo conversacion IA: {e}")
            return RespuestaIAChat(
                exito=False,
                mensaje=f"Error: {str(e)}"
            )

    def listar_conversaciones(
        self,
        usuario_id: int,
        incluir_archivadas: bool = False
    ) -> RespuestaIAChat:
        """
        Lista todas las conversaciones de un usuario con IA.
        """
        try:
            conversaciones = self.almacenamiento.obtener_conversaciones_usuario(
                usuario_id,
                incluir_archivadas
            )

            return RespuestaIAChat(
                exito=True,
                mensaje=f"{len(conversaciones)} conversaciones encontradas",
                datos={
                    'conversaciones': [
                        ConversacionIADTO.desde_entidad(c).__dict__
                        for c in conversaciones
                    ],
                    'ia_contacto': self.obtener_contacto_ia()
                }
            )
        except Exception as e:
            logger.error(f"Error listando conversaciones IA: {e}")
            return RespuestaIAChat(
                exito=False,
                mensaje=f"Error: {str(e)}"
            )

    def eliminar_conversacion(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> RespuestaIAChat:
        """
        Elimina una conversacion.
        """
        try:
            conv = self.almacenamiento.obtener_conversacion(conversacion_id)

            if not conv:
                return RespuestaIAChat(exito=False, mensaje="Conversacion no encontrada")

            if conv.usuario_id != usuario_id:
                return RespuestaIAChat(exito=False, mensaje="No tienes acceso")

            self.almacenamiento.eliminar_conversacion(conversacion_id)

            return RespuestaIAChat(
                exito=True,
                mensaje="Conversacion eliminada"
            )
        except Exception as e:
            return RespuestaIAChat(exito=False, mensaje=f"Error: {str(e)}")

    def eliminar_conversacion_permanente(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> RespuestaIAChat:
        """
        Elimina PERMANENTEMENTE una conversacion y todos sus mensajes.
        Esta accion no se puede deshacer.
        """
        try:
            # Usar metodo que no filtra por estado para poder eliminar cualquier conversacion
            conv = self.almacenamiento.obtener_conversacion_cualquier_estado(conversacion_id)

            if not conv:
                logger.warning(f"Conversacion {conversacion_id} no encontrada para eliminacion permanente")
                return RespuestaIAChat(exito=False, mensaje="Conversacion no encontrada")

            if conv.usuario_id != usuario_id:
                logger.warning(f"Usuario {usuario_id} intento eliminar conversacion {conversacion_id} de usuario {conv.usuario_id}")
                return RespuestaIAChat(exito=False, mensaje="No tienes acceso a esta conversacion")

            resultado = self.almacenamiento.eliminar_conversacion_permanente(conversacion_id)

            if resultado:
                logger.info(f"Conversacion {conversacion_id} eliminada permanentemente por usuario {usuario_id}")
                return RespuestaIAChat(
                    exito=True,
                    mensaje="Conversacion eliminada permanentemente"
                )
            else:
                return RespuestaIAChat(exito=False, mensaje="No se pudo eliminar la conversacion")

        except Exception as e:
            logger.error(f"Error eliminando conversacion {conversacion_id}: {e}")
            return RespuestaIAChat(exito=False, mensaje=f"Error: {str(e)}")

    def archivar_conversacion(
        self,
        conversacion_id: int,
        usuario_id: int,
        archivar: bool = True
    ) -> RespuestaIAChat:
        """
        Archiva o desarchiva una conversacion.
        """
        try:
            # Usar incluir_no_activas=True para poder desarchivar conversaciones archivadas
            conv = self.almacenamiento.obtener_conversacion(conversacion_id, incluir_no_activas=True)

            if not conv or conv.usuario_id != usuario_id:
                return RespuestaIAChat(exito=False, mensaje="Conversacion no encontrada")

            # Persistir el cambio en la base de datos
            resultado = self.almacenamiento.archivar_conversacion(conversacion_id, archivar)

            if resultado:
                return RespuestaIAChat(
                    exito=True,
                    mensaje="Conversacion archivada" if archivar else "Conversacion desarchivada"
                )
            else:
                return RespuestaIAChat(exito=False, mensaje="Error al archivar conversacion")
        except Exception as e:
            return RespuestaIAChat(exito=False, mensaje=f"Error: {str(e)}")

    # =========================================================================
    # ENVIO DE MENSAJES
    # =========================================================================

    def _detectar_intencion_busqueda(self, mensaje: str) -> tuple:
        """
        Detecta si el mensaje requiere busqueda web.

        Returns:
            (necesita_busqueda, intencion, confianza)
        """
        mensaje_lower = mensaje.lower()

        # Palabras clave de busqueda explicita
        busqueda_explicita = [
            'busca en internet', 'buscar en internet', 'busca en la web',
            'buscar en la web', 'busca online', 'buscar online',
            'busca en google', 'consulta en internet', 'investiga en internet',
            'que dice internet', 'segun internet', 'busca informacion sobre'
        ]

        # Palabras clave de actualidad
        actualidad = [
            'noticias', 'actual', 'hoy', 'reciente', 'ultimo', 'nueva',
            'precio', 'cotizacion', 'clima', 'tiempo en', 'dolar'
        ]

        # Verificar busqueda explicita (alta confianza)
        for frase in busqueda_explicita:
            if frase in mensaje_lower:
                return True, 'buscar_web', 0.95

        # Verificar temas de actualidad (confianza media)
        for palabra in actualidad:
            if palabra in mensaje_lower:
                return True, 'buscar_actualidad', 0.75

        return False, 'chat', 0.0

    def enviar_mensaje(
        self,
        conversacion_id: int,
        usuario_id: int,
        contenido: str,
        capacidad: CapacidadIA = CapacidadIA.CHAT
    ) -> RespuestaIAChat:
        """
        Envia un mensaje a IA Maquita y obtiene respuesta.

        Args:
            conversacion_id: ID de la conversacion
            usuario_id: ID del usuario
            contenido: Mensaje del usuario
            capacidad: Tipo de capacidad IA a usar

        Returns:
            RespuestaIAChat con mensaje del usuario, respuesta de IA,
            y multimedia de busqueda (imagenes, videos, fuentes) v3.0
        """
        try:
            # Validar conversacion
            conv = self.almacenamiento.obtener_conversacion(conversacion_id)

            if not conv:
                return RespuestaIAChat(exito=False, mensaje="Conversacion no encontrada")

            if conv.usuario_id != usuario_id:
                return RespuestaIAChat(exito=False, mensaje="No tienes acceso")

            # Validar configuracion del usuario
            config = self.almacenamiento.obtener_configuracion(usuario_id)
            if not config.puede_enviar_mensaje():
                return RespuestaIAChat(
                    exito=False,
                    mensaje="Has alcanzado el limite de mensajes diarios"
                )

            # ================================================================
            # V3.0: Detectar intencion de busqueda
            # ================================================================
            necesita_busqueda, intencion, confianza_intencion = self._detectar_intencion_busqueda(contenido)

            # Crear mensaje del usuario con intencion detectada
            msg_usuario = MensajeIA.crear_mensaje_usuario(
                conversacion_ia_id=conv.id,
                contenido=contenido
            )
            self.almacenamiento.agregar_mensaje(
                conv.id,
                msg_usuario,
                intencion_detectada=intencion if confianza_intencion > 0.5 else None
            )

            # ================================================================
            # V3.0: Busqueda web mejorada con imagenes, videos y fuentes
            # ================================================================
            contexto_adicional = ""
            uso_web = False
            resultado_busqueda = None
            imagenes_resultado = []
            videos_resultado = []
            fuentes_resultado = []

            # Primero intentar busqueda mejorada si hay intencion
            if necesita_busqueda and BUSQUEDA_MEJORADA_AVAILABLE:
                try:
                    servicio_busqueda = obtener_servicio_busqueda_mejorada()
                    resultado_busqueda = servicio_busqueda.buscar_y_registrar(
                        query=contenido,
                        mensaje_id=msg_usuario.id,
                        usuario_id=usuario_id,
                        incluir_imagenes=True,
                        incluir_videos=True,
                        max_fuentes=5,
                        max_imagenes=6,
                        max_videos=3
                    )

                    if resultado_busqueda.success:
                        uso_web = True
                        contexto_adicional = servicio_busqueda.formatear_para_contexto(resultado_busqueda)

                        # Extraer multimedia para respuesta
                        imagenes_resultado = [img.to_dict() for img in resultado_busqueda.imagenes]
                        videos_resultado = [vid.to_dict() for vid in resultado_busqueda.videos]
                        fuentes_resultado = [f.to_dict() for f in resultado_busqueda.fuentes]

                        logger.info(f"Busqueda mejorada: {len(fuentes_resultado)} fuentes, {len(imagenes_resultado)} imgs, {len(videos_resultado)} videos")

                except Exception as e:
                    logger.warning(f"Error en busqueda mejorada: {e}")

            # Fallback a conocimiento institucional si no hay busqueda o fallo
            if not contexto_adicional and KNOWLEDGE_AVAILABLE:
                try:
                    contexto_adicional = obtener_contexto_para_pregunta(contenido)
                    if "INFORMACION DE INTERNET" in contexto_adicional:
                        uso_web = True
                    logger.debug(f"Contexto conocimiento: {len(contexto_adicional)} caracteres")
                except Exception as e:
                    logger.warning(f"Error obteniendo contexto: {e}")

            # Obtener historial de contexto
            historial = conv.obtener_historial_contexto()

            # Construir mensaje con contexto si hay
            mensaje_con_contexto = contenido
            if contexto_adicional:
                mensaje_con_contexto = f"""CONTEXTO RELEVANTE PARA RESPONDER:
{contexto_adicional}

PREGUNTA DEL USUARIO:
{contenido}

Responde usando el contexto proporcionado cuando sea relevante."""

            # Agregar mensaje actual al historial
            historial.append({'role': 'user', 'content': mensaje_con_contexto})

            # Determinar modelo a usar (preferir Qwen si disponible)
            modelo_usar = config.modelo_preferido
            if modelo_usar == 'llama3.2:3b':
                modelo_usar = MODELO_IA_DEFECTO  # Usar Qwen2.5:7b

            # Enviar a Ollama
            inicio = time.time()
            respuesta_ollama = self.ollama.chat(
                messages=historial,
                model=modelo_usar,
                system=SISTEMA_IA_MAQUITA,
                temperature=config.temperatura
            )
            tiempo_respuesta = int((time.time() - inicio) * 1000)

            if not respuesta_ollama.success:
                # Error de Ollama
                msg_error = MensajeIA.crear_respuesta_ia(
                    conversacion_ia_id=conv.id,
                    contenido="Lo siento, tengo problemas para responder en este momento. Por favor, intenta de nuevo.",
                    modelo=config.modelo_preferido,
                    capacidad=capacidad
                )
                self.almacenamiento.agregar_mensaje(conv.id, msg_error)

                return RespuestaIAChat(
                    exito=False,
                    mensaje=f"Error de IA: {respuesta_ollama.error}",
                    datos={
                        'mensaje_usuario': MensajeIADTO.desde_entidad(msg_usuario).__dict__,
                        'respuesta_ia': MensajeIADTO.desde_entidad(msg_error).__dict__
                    }
                )

            # Crear respuesta de IA con multimedia v3.0
            msg_ia = MensajeIA.crear_respuesta_ia(
                conversacion_ia_id=conv.id,
                contenido=respuesta_ollama.response,
                modelo=respuesta_ollama.model,
                tiempo_respuesta_ms=tiempo_respuesta,
                capacidad=capacidad
            )

            # Guardar mensaje con multimedia de busqueda
            self.almacenamiento.agregar_mensaje(
                conv.id,
                msg_ia,
                imagenes=imagenes_resultado,
                videos=videos_resultado,
                fuentes=fuentes_resultado,
                busqueda_realizada=uso_web,
                intencion_detectada=intencion if uso_web else None
            )

            # Actualizar titulo si es el primer mensaje
            if conv.total_mensajes <= 2:
                conv.titulo = conv.generar_titulo_automatico()

            # Registrar uso
            config.registrar_uso(0)  # TODO: obtener tokens reales

            # Registrar para aprendizaje automatico
            if KNOWLEDGE_AVAILABLE:
                try:
                    knowledge_service = obtener_servicio_conocimiento()
                    knowledge_service.aprender_de_chat(
                        conversacion_id=conv.id,
                        pregunta=contenido,
                        respuesta=respuesta_ollama.response
                    )
                except Exception as e:
                    logger.warning(f"Error registrando aprendizaje: {e}")
            
            # ============================================================
            # ENTRENAMIENTO MASTER ADMIN
            # ============================================================
            # Verificar si el usuario es Master Admin para entrenamiento especial
            try:
                from .entrenamiento_master_admin import (
                    EntrenamientoMasterAdmin, 
                    detectar_intencion_entrenamiento,
                    corregir_mensaje_admin
                )
                
                # Obtener rol del usuario
                session = self.almacenamiento._get_session()
                try:
                    result = session.execute(
                        text("SELECT rol FROM usuarios WHERE id = :usuario_id LIMIT 1"),
                        {'usuario_id': usuario_id}
                    ).fetchone()
                    rol_usuario = result[0] if result else ''
                    
                    # Corregir mensaje del admin
                    contenido_corregido = corregir_mensaje_admin(contenido)
                    
                    # Detectar si quiere entrenar
                    es_entrenamiento, confianza, frase = detectar_intencion_entrenamiento(
                        contenido_corregido, rol_usuario
                    )
                    
                    if es_entrenamiento and confianza > 0.8:
                        # Crear instancia de entrenamiento
                        entrenador = EntrenamientoMasterAdmin(session)
                        
                        # Procesar como entrenamiento
                        resultado_entrenamiento = entrenador.marcar_como_entrenamiento(
                            mensaje_usuario=contenido_corregido,
                            respuesta_ia=respuesta_ollama.response,
                            usuario_id=usuario_id,
                            conversacion_id=conv.id,
                            confirmacion_admin=(confianza == 1.0)  # Confirmación explícita
                        )
                        
                        logger.info(f"Entrenamiento Master Admin: {resultado_entrenamiento}")
                        
                        # Agregar metadata a la respuesta
                        if resultado_entrenamiento['es_entrenamiento']:
                            msg_ia.metadata = msg_ia.metadata or {}
                            msg_ia.metadata['entrenamiento'] = {
                                'guardado': True,
                                'categoria': resultado_entrenamiento.get('categoria'),
                                'mensaje': resultado_entrenamiento['mensaje']
                            }
                    
                finally:
                    session.close()
                    
            except ImportError:
                # Módulo no disponible
                pass
            except Exception as e:
                logger.error(f"Error en entrenamiento Master Admin: {e}")

            logger.info(f"Mensaje IA v3.0: conv={conv.id}, tiempo={tiempo_respuesta}ms, modelo={modelo_usar}, web={uso_web}, imgs={len(imagenes_resultado)}")

            # ================================================================
            # V3.0: Respuesta enriquecida con multimedia
            # ================================================================
            return RespuestaIAChat(
                exito=True,
                mensaje="Mensaje enviado",
                datos={
                    'mensaje_usuario': MensajeIADTO.desde_entidad(msg_usuario).__dict__,
                    'respuesta_ia': MensajeIADTO.desde_entidad(msg_ia).__dict__,
                    'conversacion_titulo': conv.titulo,
                    'uso_contexto': bool(contexto_adicional),
                    'uso_web': uso_web,
                    'modelo_usado': modelo_usar,
                    # V3.0: Multimedia de busqueda
                    'imagenes': imagenes_resultado,
                    'videos': videos_resultado,
                    'fuentes': fuentes_resultado,
                    'intencion_detectada': intencion if confianza_intencion > 0.5 else None,
                    'tiempo_busqueda_ms': resultado_busqueda.tiempo_busqueda_ms if resultado_busqueda else 0
                }
            )

        except Exception as e:
            logger.error(f"Error enviando mensaje IA: {e}")
            return RespuestaIAChat(
                exito=False,
                mensaje=f"Error: {str(e)}"
            )

    def obtener_mensajes(
        self,
        conversacion_id: int,
        usuario_id: int,
        limite: int = 50,
        offset: int = 0
    ) -> RespuestaIAChat:
        """
        Obtiene los mensajes de una conversacion.
        """
        try:
            conv = self.almacenamiento.obtener_conversacion(conversacion_id)

            if not conv or conv.usuario_id != usuario_id:
                return RespuestaIAChat(exito=False, mensaje="Conversacion no encontrada")

            mensajes = conv.mensajes[offset:offset + limite]

            return RespuestaIAChat(
                exito=True,
                mensaje=f"{len(mensajes)} mensajes",
                datos={
                    'mensajes': [MensajeIADTO.desde_entidad(m).__dict__ for m in mensajes],
                    'total': len(conv.mensajes),
                    'tiene_mas': offset + limite < len(conv.mensajes)
                }
            )
        except Exception as e:
            return RespuestaIAChat(exito=False, mensaje=f"Error: {str(e)}")

    # =========================================================================
    # CONFIGURACION DE USUARIO
    # =========================================================================

    def obtener_configuracion_usuario(self, usuario_id: int) -> RespuestaIAChat:
        """Obtiene la configuracion de IA para un usuario."""
        try:
            config = self.almacenamiento.obtener_configuracion(usuario_id)
            return RespuestaIAChat(
                exito=True,
                mensaje="Configuracion obtenida",
                datos={'configuracion': config.to_dict()}
            )
        except Exception as e:
            return RespuestaIAChat(exito=False, mensaje=f"Error: {str(e)}")

    def actualizar_configuracion_usuario(
        self,
        usuario_id: int,
        temperatura: float = None,
        modelo: str = None
    ) -> RespuestaIAChat:
        """Actualiza la configuracion de IA para un usuario."""
        try:
            config = self.almacenamiento.obtener_configuracion(usuario_id)

            if temperatura is not None:
                config.temperatura = max(0.0, min(1.0, temperatura))
            if modelo:
                config.modelo_preferido = modelo

            config.actualizado_en = datetime.now()
            self.almacenamiento.actualizar_configuracion(config)

            return RespuestaIAChat(
                exito=True,
                mensaje="Configuracion actualizada",
                datos={'configuracion': config.to_dict()}
            )
        except Exception as e:
            return RespuestaIAChat(exito=False, mensaje=f"Error: {str(e)}")


# Instancia singleton del servicio
_servicio_ia_chat = None


def obtener_servicio_ia_chat() -> ServicioIAChat:
    """Obtiene la instancia singleton del servicio."""
    global _servicio_ia_chat, _almacenamiento_ia

    if _servicio_ia_chat is None:
        # Inicializar almacenamiento (PostgreSQL o memoria)
        if _almacenamiento_ia is None:
            _almacenamiento_ia = _obtener_almacenamiento()
        _servicio_ia_chat = ServicioIAChat(almacenamiento=_almacenamiento_ia)

    return _servicio_ia_chat
