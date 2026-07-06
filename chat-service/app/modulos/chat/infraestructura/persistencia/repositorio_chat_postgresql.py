# -*- coding: utf-8 -*-
"""
Adaptador: Repositorios Chat PostgreSQL - Modulo Chat

Implementa las interfaces de repositorio del chat usando SQLAlchemy y PostgreSQL.

CAPA: infraestructura/persistencia
REGLAS:
- Implementa interfaces de dominio
- Puede usar SQLAlchemy y tecnologias de BD

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado a modulos: 2026-01-05
"""

from typing import Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func, desc, nullslast

# Importar interfaces de dominio desde el modulo chat
from modulos.chat.dominio.repositorios.repositorio_chat import (
    RepositorioConversacion,
    RepositorioParticipante,
    RepositorioMensaje,
    RepositorioArchivoMensaje,
    RepositorioReaccion,
    RepositorioPresencia,
    RepositorioBloqueo,
    RepositorioIndicadorAccion
)
from modulos.chat.dominio.entidades.conversacion import Conversacion, Participante
from modulos.chat.dominio.entidades.mensaje import Mensaje, ArchivoMensaje, ReaccionMensaje
from modulos.chat.dominio.value_objects.tipos_chat import (
    TipoConversacion,
    TipoMensaje,
    TipoMedia,
    RolParticipante
)

# Importar modelos desde el modulo chat
from modulos.chat.infraestructura.persistencia.modelos import (
    ModeloConversacion,
    ModeloParticipante,
    ModeloMensaje,
    ModeloMediaMensaje,
    ModeloEstadoMensaje,
    ModeloReaccion,
    ModeloPresencia,
    ModeloBloqueo,
    ModeloIndicadorAccion,
)


# =============================================================================
# REPOSITORIO CONVERSACION
# =============================================================================

class RepositorioConversacionPostgreSQL(RepositorioConversacion):
    """Implementacion PostgreSQL del repositorio de conversaciones."""

    def __init__(self, session: Session):
        self._session = session

    def buscar_por_id(self, conversacion_id: int) -> Optional[Conversacion]:
        modelo = self._session.query(ModeloConversacion).filter_by(
            id=conversacion_id
        ).first()
        return self._a_entidad(modelo) if modelo else None

    def buscar_por_public_id(self, public_id: str) -> Optional[Conversacion]:
        modelo = self._session.query(ModeloConversacion).filter_by(
            public_id=public_id
        ).first()
        return self._a_entidad(modelo) if modelo else None

    def obtener_conversaciones_usuario(
        self,
        usuario_id: int,
        limite: int = 20,
        offset: int = 0
    ) -> List[Conversacion]:
        subquery = self._session.query(ModeloParticipante.conversation_id).filter(
            ModeloParticipante.user_id == usuario_id,
            ModeloParticipante.is_active == True
        )

        modelos = self._session.query(ModeloConversacion).filter(
            ModeloConversacion.id.in_(subquery),
            ModeloConversacion.is_active == True
        ).order_by(
            nullslast(desc(ModeloConversacion.last_message_at))
        ).offset(offset).limit(limite).all()

        return [self._a_entidad(m) for m in modelos]

    def buscar_directa(
        self,
        usuario1_id: int,
        usuario2_id: int
    ) -> Optional[Conversacion]:
        subquery1 = self._session.query(ModeloParticipante.conversation_id).filter(
            ModeloParticipante.user_id == usuario1_id,
            ModeloParticipante.is_active == True
        )
        subquery2 = self._session.query(ModeloParticipante.conversation_id).filter(
            ModeloParticipante.user_id == usuario2_id,
            ModeloParticipante.is_active == True
        )

        modelo = self._session.query(ModeloConversacion).filter(
            ModeloConversacion.conversation_type == 'direct',
            ModeloConversacion.id.in_(subquery1),
            ModeloConversacion.id.in_(subquery2),
            ModeloConversacion.is_active == True
        ).first()

        return self._a_entidad(modelo) if modelo else None

    def crear(self, conversacion: Conversacion) -> Conversacion:
        modelo = ModeloConversacion(
            public_id=conversacion.public_id,
            conversation_type=conversacion.tipo.value,
            name=conversacion.nombre,
            description=conversacion.descripcion,
            avatar_path=conversacion.avatar_ruta,
            created_by=conversacion.creador_id,
            last_message_at=conversacion.ultimo_mensaje_en,
            last_message_preview=conversacion.ultimo_mensaje_preview,
            is_active=conversacion.activa,
            settings=conversacion.configuracion or {},
            created_at=conversacion.creada_en or datetime.now(),
            updated_at=datetime.now()
        )
        self._session.add(modelo)
        self._session.flush()
        conversacion.id = modelo.id
        return conversacion

    def actualizar(self, conversacion: Conversacion) -> Conversacion:
        modelo = self._session.query(ModeloConversacion).filter_by(
            id=conversacion.id
        ).first()
        if modelo:
            modelo.name = conversacion.nombre
            modelo.description = conversacion.descripcion
            modelo.avatar_path = conversacion.avatar_ruta
            modelo.is_active = conversacion.activa
            modelo.settings = conversacion.configuracion or {}
            modelo.updated_at = datetime.now()
            self._session.flush()
        return conversacion

    def actualizar_ultimo_mensaje(
        self,
        conversacion_id: int,
        contenido: str,
        fecha: datetime
    ) -> None:
        modelo = self._session.query(ModeloConversacion).filter_by(
            id=conversacion_id
        ).first()
        if modelo:
            modelo.last_message_at = fecha
            modelo.last_message_preview = contenido[:100] if contenido else None
            modelo.updated_at = datetime.now()
            self._session.flush()

    def _a_entidad(self, modelo: ModeloConversacion) -> Conversacion:
        tipo = TipoConversacion.GRUPO if modelo.conversation_type == 'group' else TipoConversacion.DIRECTA
        return Conversacion(
            id=modelo.id,
            public_id=modelo.public_id,
            tipo=tipo,
            nombre=modelo.name,
            descripcion=modelo.description,
            avatar_ruta=modelo.avatar_path,
            creador_id=modelo.created_by,
            ultimo_mensaje_en=modelo.last_message_at,
            ultimo_mensaje_preview=modelo.last_message_preview,
            activa=modelo.is_active,
            configuracion=modelo.settings or {},
            creada_en=modelo.created_at,
            actualizada_en=modelo.updated_at
        )


# =============================================================================
# REPOSITORIO PARTICIPANTE
# =============================================================================

class RepositorioParticipantePostgreSQL(RepositorioParticipante):
    """Implementacion PostgreSQL del repositorio de participantes."""

    def __init__(self, session: Session):
        self._session = session

    def buscar_por_id(self, participante_id: int) -> Optional[Participante]:
        modelo = self._session.query(ModeloParticipante).filter_by(
            id=participante_id
        ).first()
        return self._a_entidad(modelo) if modelo else None

    def buscar_en_conversacion(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> Optional[Participante]:
        modelo = self._session.query(ModeloParticipante).filter_by(
            conversation_id=conversacion_id,
            user_id=usuario_id
        ).first()
        return self._a_entidad(modelo) if modelo else None

    def obtener_participantes(
        self,
        conversacion_id: int,
        solo_activos: bool = True
    ) -> List[Participante]:
        query = self._session.query(ModeloParticipante).filter_by(
            conversation_id=conversacion_id
        )
        if solo_activos:
            query = query.filter_by(is_active=True)
        modelos = query.all()
        return [self._a_entidad(m) for m in modelos]

    def agregar(self, participante: Participante) -> Participante:
        modelo = ModeloParticipante(
            conversation_id=participante.conversacion_id,
            user_id=participante.usuario_id,
            role=participante.rol.value,
            nickname=participante.apodo,
            is_muted=participante.silenciado,
            muted_until=participante.silenciado_hasta,
            is_active=participante.activo,
            joined_at=participante.unido_en or datetime.now()
        )
        self._session.add(modelo)
        self._session.flush()
        participante.id = modelo.id
        return participante

    def agregar_varios(
        self,
        conversacion_id: int,
        usuario_ids: List[int],
        rol: RolParticipante = RolParticipante.MIEMBRO
    ) -> List[Participante]:
        participantes = []
        for usuario_id in usuario_ids:
            modelo = ModeloParticipante(
                conversation_id=conversacion_id,
                user_id=usuario_id,
                role=rol.value,
                is_active=True,
                joined_at=datetime.now()
            )
            self._session.add(modelo)
            self._session.flush()
            participantes.append(self._a_entidad(modelo))
        return participantes

    def actualizar(self, participante: Participante) -> Participante:
        modelo = self._session.query(ModeloParticipante).filter_by(
            id=participante.id
        ).first()
        if modelo:
            modelo.role = participante.rol.value
            modelo.nickname = participante.apodo
            modelo.is_muted = participante.silenciado
            modelo.muted_until = participante.silenciado_hasta
            modelo.is_active = participante.activo
            self._session.flush()
        return participante

    def desactivar(self, conversacion_id: int, usuario_id: int) -> bool:
        modelo = self._session.query(ModeloParticipante).filter_by(
            conversation_id=conversacion_id,
            user_id=usuario_id
        ).first()
        if modelo:
            modelo.is_active = False
            modelo.left_at = datetime.now()
            self._session.flush()
            return True
        return False

    def marcar_leido(
        self,
        conversacion_id: int,
        usuario_id: int,
        hasta_mensaje_id: int
    ) -> None:
        modelo = self._session.query(ModeloParticipante).filter_by(
            conversation_id=conversacion_id,
            user_id=usuario_id
        ).first()
        if modelo:
            modelo.last_read_message_id = hasta_mensaje_id
            modelo.last_read_at = datetime.now()
            modelo.unread_count = 0
            self._session.flush()

    def obtener_no_leidos(self, usuario_id: int) -> int:
        resultado = self._session.query(
            func.sum(ModeloParticipante.unread_count)
        ).filter(
            ModeloParticipante.user_id == usuario_id,
            ModeloParticipante.is_active == True
        ).scalar()
        return resultado or 0

    def _a_entidad(self, modelo: ModeloParticipante) -> Participante:
        rol_map = {
            'admin': RolParticipante.ADMIN,
            'moderator': RolParticipante.MODERADOR,
            'member': RolParticipante.MIEMBRO
        }
        return Participante(
            id=modelo.id,
            conversacion_id=modelo.conversation_id,
            usuario_id=modelo.user_id,
            rol=rol_map.get(modelo.role, RolParticipante.MIEMBRO),
            apodo=modelo.nickname,
            silenciado=modelo.is_muted,
            silenciado_hasta=modelo.muted_until,
            activo=modelo.is_active,
            ultimo_mensaje_leido_id=modelo.last_read_message_id,
            ultimo_leido_en=modelo.last_read_at,
            mensajes_no_leidos=modelo.unread_count or 0,
            unido_en=modelo.joined_at
        )


# =============================================================================
# REPOSITORIO MENSAJE
# =============================================================================

class RepositorioMensajePostgreSQL(RepositorioMensaje):
    """Implementacion PostgreSQL del repositorio de mensajes."""

    def __init__(self, session: Session):
        self._session = session

    def buscar_por_id(self, mensaje_id: int) -> Optional[Mensaje]:
        modelo = self._session.query(ModeloMensaje).options(
            joinedload(ModeloMensaje.media)
        ).filter_by(id=mensaje_id).first()
        return self._a_entidad(modelo) if modelo else None

    def buscar_por_public_id(self, public_id: str) -> Optional[Mensaje]:
        modelo = self._session.query(ModeloMensaje).options(
            joinedload(ModeloMensaje.media)
        ).filter_by(public_id=public_id).first()
        return self._a_entidad(modelo) if modelo else None

    def buscar_por_client_id(self, client_id: str) -> Optional[Mensaje]:
        """Busca mensaje por client_id para idempotencia."""
        modelo = self._session.query(ModeloMensaje).options(
            joinedload(ModeloMensaje.media)
        ).filter_by(client_id=client_id).first()
        return self._a_entidad(modelo) if modelo else None

    def obtener_mensajes(
        self,
        conversacion_id: int,
        limite: int = 50,
        antes_de_id: Optional[int] = None
    ) -> List[Mensaje]:
        query = self._session.query(ModeloMensaje).options(
            joinedload(ModeloMensaje.media)
        ).filter_by(
            conversation_id=conversacion_id
        )

        if antes_de_id:
            query = query.filter(ModeloMensaje.id < antes_de_id)

        modelos = query.order_by(desc(ModeloMensaje.created_at)).limit(limite).all()
        return [self._a_entidad(m) for m in modelos]

    def crear(self, mensaje: Mensaje) -> Mensaje:
        modelo = ModeloMensaje(
            public_id=mensaje.public_id,
            conversation_id=mensaje.conversacion_id,
            sender_id=mensaje.remitente_id,
            content=mensaje.contenido,
            message_type=mensaje.tipo.value,
            reply_to_id=mensaje.respuesta_a_id,
            forwarded_from_id=mensaje.reenviado_de_id,
            is_edited=mensaje.editado,
            is_deleted=mensaje.eliminado,
            msg_metadata=mensaje.metadata or {},
            created_at=mensaje.creado_en or datetime.now(),
            updated_at=datetime.now(),
            client_id=getattr(mensaje, 'client_id', None)
        )
        self._session.add(modelo)
        self._session.flush()
        mensaje.id = modelo.id
        return mensaje

    def actualizar(self, mensaje: Mensaje) -> Mensaje:
        modelo = self._session.query(ModeloMensaje).filter_by(
            id=mensaje.id
        ).first()
        if modelo:
            modelo.content = mensaje.contenido
            modelo.is_edited = mensaje.editado
            modelo.is_deleted = mensaje.eliminado
            modelo.deleted_at = mensaje.eliminado_en
            modelo.deleted_for_everyone = mensaje.eliminado_para_todos
            modelo.updated_at = datetime.now()
            self._session.flush()
        return mensaje

    def eliminar(self, mensaje_id: int, para_todos: bool = False) -> bool:
        modelo = self._session.query(ModeloMensaje).filter_by(
            id=mensaje_id
        ).first()
        if modelo:
            modelo.is_deleted = True
            modelo.deleted_at = datetime.now(timezone.utc)
            modelo.deleted_for_everyone = para_todos
            if para_todos:
                modelo.content = None
            self._session.flush()
            return True
        return False

    def buscar(
        self,
        usuario_id: int,
        consulta: str,
        conversacion_id: Optional[int] = None,
        limite: int = 50
    ) -> List[Mensaje]:
        subquery = self._session.query(ModeloParticipante.conversation_id).filter(
            ModeloParticipante.user_id == usuario_id,
            ModeloParticipante.is_active == True
        ).subquery()

        query = self._session.query(ModeloMensaje).filter(
            ModeloMensaje.conversation_id.in_(subquery),
            ModeloMensaje.is_deleted == False,
            ModeloMensaje.content.ilike(f'%{consulta}%')
        )

        if conversacion_id:
            query = query.filter(ModeloMensaje.conversation_id == conversacion_id)

        modelos = query.order_by(desc(ModeloMensaje.created_at)).limit(limite).all()
        return [self._a_entidad(m) for m in modelos]

    def obtener_fijados(self, conversacion_id: int) -> List[Mensaje]:
        """Obtiene los mensajes fijados de una conversacion."""
        modelos = self._session.query(ModeloMensaje).options(
            joinedload(ModeloMensaje.media)
        ).filter(
            ModeloMensaje.conversation_id == conversacion_id,
            ModeloMensaje.is_pinned == True
        ).order_by(desc(ModeloMensaje.pinned_at)).all()
        return [self._a_entidad(m) for m in modelos]

    def fijar_mensaje(self, mensaje_id: int, usuario_id: int) -> None:
        """Fija un mensaje."""
        modelo = self._session.query(ModeloMensaje).filter_by(id=mensaje_id).first()
        if modelo:
            modelo.is_pinned = True
            modelo.pinned_at = datetime.now(timezone.utc)
            modelo.pinned_by = usuario_id
            self._session.flush()

    def desfijar_mensaje(self, mensaje_id: int) -> None:
        """Desfija un mensaje."""
        modelo = self._session.query(ModeloMensaje).filter_by(id=mensaje_id).first()
        if modelo:
            modelo.is_pinned = False
            modelo.pinned_at = None
            modelo.pinned_by = None
            self._session.flush()

    def contar_no_leidos(
        self,
        conversacion_id: int,
        usuario_id: int,
        desde_mensaje_id: Optional[int] = None
    ) -> int:
        query = self._session.query(func.count(ModeloMensaje.id)).filter(
            ModeloMensaje.conversation_id == conversacion_id,
            ModeloMensaje.sender_id != usuario_id,
            ModeloMensaje.is_deleted == False
        )
        if desde_mensaje_id:
            query = query.filter(ModeloMensaje.id > desde_mensaje_id)
        return query.scalar() or 0

    def _a_entidad(self, modelo: ModeloMensaje) -> Mensaje:
        tipo_map = {
            'text': TipoMensaje.TEXTO,
            'image': TipoMensaje.IMAGEN,
            'video': TipoMensaje.VIDEO,
            'audio': TipoMensaje.AUDIO,
            'document': TipoMensaje.DOCUMENTO,
            'sticker': TipoMensaje.STICKER,
            'gif': TipoMensaje.GIF,
            'location': TipoMensaje.UBICACION,
            'contact': TipoMensaje.CONTACTO,
            'system': TipoMensaje.SISTEMA,
            'reply': TipoMensaje.RESPUESTA,
            'forwarded': TipoMensaje.REENVIADO
        }

        archivos = []
        if modelo.media:
            for media in modelo.media:
                archivos.append(ArchivoMensaje(
                    id=media.id,
                    mensaje_id=media.message_id,
                    tipo=TipoMedia(media.media_type),
                    ruta=media.file_path,
                    nombre=media.file_name,
                    tamanio=media.file_size,
                    tipo_mime=media.mime_type or '',
                    ancho=media.width,
                    alto=media.height,
                    duracion=media.duration,
                    miniatura_ruta=media.thumbnail_path,
                    orden=media.display_order or 0
                ))

        return Mensaje(
            id=modelo.id,
            public_id=modelo.public_id,
            conversacion_id=modelo.conversation_id,
            remitente_id=modelo.sender_id,
            contenido=modelo.content,
            tipo=tipo_map.get(modelo.message_type, TipoMensaje.TEXTO),
            respuesta_a_id=modelo.reply_to_id,
            reenviado_de_id=modelo.forwarded_from_id,
            editado=modelo.is_edited,
            eliminado=modelo.is_deleted,
            eliminado_en=modelo.deleted_at,
            eliminado_para_todos=modelo.deleted_for_everyone or False,
            metadata=modelo.msg_metadata or {},
            fijado=getattr(modelo, 'is_pinned', False) or False,
            fijado_en=getattr(modelo, 'pinned_at', None),
            fijado_por=getattr(modelo, 'pinned_by', None),
            creado_en=modelo.created_at,
            actualizado_en=modelo.updated_at,
            archivos=archivos
        )


# =============================================================================
# REPOSITORIO ARCHIVO MENSAJE
# =============================================================================

class RepositorioArchivoMensajePostgreSQL(RepositorioArchivoMensaje):
    """Implementacion PostgreSQL del repositorio de archivos de mensajes."""

    def __init__(self, session: Session):
        self._session = session

    def buscar_por_id(self, archivo_id: int) -> Optional[ArchivoMensaje]:
        modelo = self._session.query(ModeloMediaMensaje).filter_by(
            id=archivo_id
        ).first()
        return self._a_entidad(modelo) if modelo else None

    def obtener_archivos_mensaje(self, mensaje_id: int) -> List[ArchivoMensaje]:
        modelos = self._session.query(ModeloMediaMensaje).filter_by(
            message_id=mensaje_id
        ).order_by(ModeloMediaMensaje.display_order).all()
        return [self._a_entidad(m) for m in modelos]

    def crear(self, archivo: ArchivoMensaje) -> ArchivoMensaje:
        modelo = ModeloMediaMensaje(
            message_id=archivo.mensaje_id,
            media_type=archivo.tipo.value,
            file_path=archivo.ruta,
            file_name=archivo.nombre,
            file_size=archivo.tamanio,
            mime_type=archivo.tipo_mime,
            width=archivo.ancho,
            height=archivo.alto,
            duration=archivo.duracion,
            thumbnail_path=archivo.miniatura_ruta,
            display_order=archivo.orden,
            created_at=datetime.now()
        )
        self._session.add(modelo)
        self._session.flush()
        archivo.id = modelo.id
        return archivo

    def crear_varios(self, archivos: List[ArchivoMensaje]) -> List[ArchivoMensaje]:
        resultado = []
        for archivo in archivos:
            resultado.append(self.crear(archivo))
        return resultado

    def eliminar(self, archivo_id: int) -> bool:
        modelo = self._session.query(ModeloMediaMensaje).filter_by(
            id=archivo_id
        ).first()
        if modelo:
            self._session.delete(modelo)
            self._session.flush()
            return True
        return False

    def _a_entidad(self, modelo: ModeloMediaMensaje) -> ArchivoMensaje:
        return ArchivoMensaje(
            id=modelo.id,
            mensaje_id=modelo.message_id,
            tipo=TipoMedia(modelo.media_type),
            ruta=modelo.file_path,
            nombre=modelo.file_name,
            tamanio=modelo.file_size,
            tipo_mime=modelo.mime_type or '',
            ancho=modelo.width,
            alto=modelo.height,
            duracion=modelo.duration,
            miniatura_ruta=modelo.thumbnail_path,
            orden=modelo.display_order or 0
        )


# =============================================================================
# REPOSITORIO REACCION
# =============================================================================

class RepositorioReaccionPostgreSQL(RepositorioReaccion):
    """Implementacion PostgreSQL del repositorio de reacciones."""

    def __init__(self, session: Session):
        self._session = session

    def buscar(
        self,
        mensaje_id: int,
        usuario_id: int
    ) -> Optional[ReaccionMensaje]:
        modelo = self._session.query(ModeloReaccion).filter_by(
            message_id=mensaje_id,
            user_id=usuario_id
        ).first()
        return self._a_entidad(modelo) if modelo else None

    def obtener_reacciones_mensaje(
        self,
        mensaje_id: int
    ) -> List[ReaccionMensaje]:
        try:
            modelos = self._session.query(ModeloReaccion).filter_by(
                message_id=mensaje_id
            ).all()
            return [self._a_entidad(m) for m in modelos]
        except Exception:
            return []

    def agregar(self, reaccion: ReaccionMensaje) -> ReaccionMensaje:
        modelo = self._session.query(ModeloReaccion).filter_by(
            message_id=reaccion.mensaje_id,
            user_id=reaccion.usuario_id
        ).first()

        if modelo:
            modelo.emoji = reaccion.emoji
            modelo.created_at = datetime.now()
        else:
            modelo = ModeloReaccion(
                message_id=reaccion.mensaje_id,
                user_id=reaccion.usuario_id,
                emoji=reaccion.emoji,
                created_at=datetime.now()
            )
            self._session.add(modelo)

        self._session.flush()
        reaccion.id = modelo.id
        reaccion.creada_en = modelo.created_at
        return reaccion

    def eliminar(self, mensaje_id: int, usuario_id: int) -> bool:
        modelo = self._session.query(ModeloReaccion).filter_by(
            message_id=mensaje_id,
            user_id=usuario_id
        ).first()
        if modelo:
            self._session.delete(modelo)
            self._session.flush()
            return True
        return False

    def contar_por_emoji(self, mensaje_id: int) -> dict:
        resultados = self._session.query(
            ModeloReaccion.emoji,
            func.count(ModeloReaccion.id)
        ).filter_by(
            message_id=mensaje_id
        ).group_by(ModeloReaccion.emoji).all()

        return {emoji: count for emoji, count in resultados}

    def _a_entidad(self, modelo: ModeloReaccion) -> ReaccionMensaje:
        return ReaccionMensaje(
            id=modelo.id,
            mensaje_id=modelo.message_id,
            usuario_id=modelo.user_id,
            emoji=modelo.emoji,
            creada_en=modelo.created_at
        )


# =============================================================================
# REPOSITORIO PRESENCIA
# =============================================================================

class RepositorioPresenciaPostgreSQL(RepositorioPresencia):
    """Implementacion PostgreSQL del repositorio de presencia."""

    def __init__(self, session: Session):
        self._session = session

    def actualizar_presencia(self, usuario_id: int, en_linea: bool = True) -> None:
        modelo = self._session.query(ModeloPresencia).filter_by(
            user_id=usuario_id
        ).first()

        if modelo:
            modelo.is_online = en_linea
            if not en_linea:
                modelo.last_seen_at = datetime.now()
            modelo.updated_at = datetime.now()
        else:
            modelo = ModeloPresencia(
                user_id=usuario_id,
                is_online=en_linea,
                last_seen_at=None if en_linea else datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            self._session.add(modelo)

        self._session.flush()

    def obtener_presencia(self, usuario_id: int) -> Tuple[bool, Optional[datetime]]:
        modelo = self._session.query(ModeloPresencia).filter_by(
            user_id=usuario_id
        ).first()

        if modelo:
            return (modelo.is_online or False, modelo.last_seen_at)
        return (False, None)

    def obtener_presencia_multiple(
        self,
        usuario_ids: List[int]
    ) -> dict:
        modelos = self._session.query(ModeloPresencia).filter(
            ModeloPresencia.user_id.in_(usuario_ids)
        ).all()

        resultado = {}
        for modelo in modelos:
            resultado[modelo.user_id] = {
                'online': modelo.is_online or False,
                'last_seen': modelo.last_seen_at
            }

        for user_id in usuario_ids:
            if user_id not in resultado:
                resultado[user_id] = {'online': False, 'last_seen': None}

        return resultado

    def marcar_offline(self, usuario_id: int) -> None:
        self.actualizar_presencia(usuario_id, en_linea=False)


# =============================================================================
# REPOSITORIO BLOQUEO
# =============================================================================

class RepositorioBloqueoPostgreSQL(RepositorioBloqueo):
    """Implementacion PostgreSQL del repositorio de bloqueos."""

    def __init__(self, session: Session):
        self._session = session

    def esta_bloqueado(
        self,
        bloqueador_id: int,
        bloqueado_id: int
    ) -> bool:
        return self._session.query(ModeloBloqueo).filter_by(
            blocker_id=bloqueador_id,
            blocked_id=bloqueado_id
        ).count() > 0

    def hay_bloqueo_mutuo(
        self,
        usuario1_id: int,
        usuario2_id: int
    ) -> bool:
        count = self._session.query(ModeloBloqueo).filter(
            or_(
                and_(
                    ModeloBloqueo.blocker_id == usuario1_id,
                    ModeloBloqueo.blocked_id == usuario2_id
                ),
                and_(
                    ModeloBloqueo.blocker_id == usuario2_id,
                    ModeloBloqueo.blocked_id == usuario1_id
                )
            )
        ).count()
        return count > 0

    def bloquear(
        self,
        bloqueador_id: int,
        bloqueado_id: int,
        razon: Optional[str] = None
    ) -> bool:
        if self.esta_bloqueado(bloqueador_id, bloqueado_id):
            return False

        modelo = ModeloBloqueo(
            blocker_id=bloqueador_id,
            blocked_id=bloqueado_id,
            reason=razon,
            created_at=datetime.now()
        )
        self._session.add(modelo)
        self._session.flush()
        return True

    def desbloquear(
        self,
        bloqueador_id: int,
        bloqueado_id: int
    ) -> bool:
        modelo = self._session.query(ModeloBloqueo).filter_by(
            blocker_id=bloqueador_id,
            blocked_id=bloqueado_id
        ).first()
        if modelo:
            self._session.delete(modelo)
            self._session.flush()
            return True
        return False

    def obtener_bloqueados(self, usuario_id: int) -> List[int]:
        modelos = self._session.query(ModeloBloqueo.blocked_id).filter_by(
            blocker_id=usuario_id
        ).all()
        return [m[0] for m in modelos]


# =============================================================================
# REPOSITORIO INDICADOR ACCION
# =============================================================================

class RepositorioIndicadorAccionPostgreSQL(RepositorioIndicadorAccion):
    """
    Implementacion PostgreSQL del repositorio de indicadores de accion.

    Maneja estados como: escribiendo, grabando audio/video, etc.
    """

    def __init__(self, session: Session):
        self._session = session

    def establecer_accion(
        self,
        conversacion_id: int,
        usuario_id: int,
        accion: str
    ) -> None:
        modelo = self._session.query(ModeloIndicadorAccion).filter_by(
            conversation_id=conversacion_id,
            user_id=usuario_id
        ).first()

        if modelo:
            modelo.started_at = datetime.now()
        else:
            modelo = ModeloIndicadorAccion(
                conversation_id=conversacion_id,
                user_id=usuario_id,
                started_at=datetime.now()
            )
            self._session.add(modelo)

        self._session.flush()

    def limpiar_accion(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> None:
        self._session.query(ModeloIndicadorAccion).filter_by(
            conversation_id=conversacion_id,
            user_id=usuario_id
        ).delete()
        self._session.flush()

    def obtener_acciones_conversacion(
        self,
        conversacion_id: int,
        excepto_usuario_id: Optional[int] = None
    ) -> List[Tuple[int, str, datetime]]:
        limite = datetime.now() - timedelta(seconds=10)

        query = self._session.query(ModeloIndicadorAccion).filter(
            ModeloIndicadorAccion.conversation_id == conversacion_id,
            ModeloIndicadorAccion.started_at >= limite
        )

        if excepto_usuario_id:
            query = query.filter(ModeloIndicadorAccion.user_id != excepto_usuario_id)

        modelos = query.all()
        return [(m.user_id, "typing", m.started_at) for m in modelos]

    def limpiar_acciones_expiradas(self, segundos: int = 10) -> int:
        limite = datetime.now() - timedelta(seconds=segundos)

        count = self._session.query(ModeloIndicadorAccion).filter(
            ModeloIndicadorAccion.started_at < limite
        ).delete()

        self._session.flush()
        return count
