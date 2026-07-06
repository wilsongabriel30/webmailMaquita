# -*- coding: utf-8 -*-
"""
Entidad de Dominio: Mensaje

Representa un mensaje en una conversacion de chat.

CAPA: modulos/chat/dominio/entidades
ARQUITECTURA: Hexagonal - 100%

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado: 2026-01-05
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from modulos.chat.dominio.value_objects.tipos_chat import (
    TipoMensaje,
    TipoMedia,
    EstadoMensaje,
    ConstantesChat,
    ContenidoMensaje,
    InfoArchivo,
    UbicacionMensaje,
    ContactoMensaje
)


@dataclass
class ArchivoMensaje:
    """
    Entidad que representa un archivo adjunto a un mensaje.
    """
    id: Optional[int]
    mensaje_id: int
    tipo: TipoMedia
    ruta: str
    nombre: str
    tamanio: int
    tipo_mime: str
    ancho: Optional[int] = None
    alto: Optional[int] = None
    duracion: Optional[int] = None  # segundos para audio/video
    miniatura_ruta: Optional[str] = None
    orden: int = 0

    def es_imagen(self) -> bool:
        return self.tipo == TipoMedia.IMAGEN

    def es_video(self) -> bool:
        return self.tipo == TipoMedia.VIDEO

    def es_audio(self) -> bool:
        return self.tipo == TipoMedia.AUDIO

    def es_documento(self) -> bool:
        return self.tipo == TipoMedia.DOCUMENTO

    def tamanio_legible(self) -> str:
        """Retorna el tamanio en formato legible."""
        if self.tamanio < 1024:
            return f"{self.tamanio} B"
        elif self.tamanio < 1024 * 1024:
            return f"{self.tamanio / 1024:.1f} KB"
        else:
            return f"{self.tamanio / (1024 * 1024):.1f} MB"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'tipo': self.tipo.value,
            'ruta': self.ruta,
            'nombre': self.nombre,
            'tamanio': self.tamanio,
            'tamanio_legible': self.tamanio_legible(),
            'tipo_mime': self.tipo_mime,
            'ancho': self.ancho,
            'alto': self.alto,
            'duracion': self.duracion,
            'miniatura_ruta': self.miniatura_ruta,
        }


@dataclass
class ReaccionMensaje:
    """
    Entidad que representa una reaccion emoji a un mensaje.
    """
    id: Optional[int]
    mensaje_id: int
    usuario_id: int
    emoji: str
    creada_en: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'usuario_id': self.usuario_id,
            'emoji': self.emoji,
            'creada_en': self.creada_en.isoformat() if self.creada_en else None,
        }


@dataclass
class EstadoEntregaMensaje:
    """
    Entidad que representa el estado de entrega de un mensaje a un usuario.
    """
    id: Optional[int]
    mensaje_id: int
    usuario_id: int
    entregado: bool = False
    entregado_en: Optional[datetime] = None
    leido: bool = False
    leido_en: Optional[datetime] = None

    @property
    def estado(self) -> EstadoMensaje:
        if self.leido:
            return EstadoMensaje.LEIDO
        if self.entregado:
            return EstadoMensaje.ENTREGADO
        return EstadoMensaje.ENVIADO


@dataclass
class Mensaje:
    """
    Entidad que representa un mensaje en el chat.

    Tipos de mensaje:
    - Texto: Mensaje de texto simple
    - Imagen/Video/Audio/Documento: Con archivos adjuntos
    - Sistema: Notificaciones (usuario unido, grupo creado, etc.)
    - Respuesta: Respuesta a otro mensaje
    - Reenviado: Mensaje reenviado de otra conversacion
    """
    id: Optional[int]
    public_id: UUID
    conversacion_id: int
    remitente_id: int
    contenido: Optional[str]
    tipo: TipoMensaje
    respuesta_a_id: Optional[int] = None
    reenviado_de_id: Optional[int] = None
    editado: bool = False
    eliminado: bool = False
    eliminado_en: Optional[datetime] = None
    eliminado_para_todos: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    fijado: bool = False
    fijado_en: Optional[datetime] = None
    fijado_por: Optional[int] = None
    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None

    # Relaciones (cargadas por el repositorio)
    archivos: List[ArchivoMensaje] = field(default_factory=list)
    reacciones: List[ReaccionMensaje] = field(default_factory=list)
    estados_entrega: List[EstadoEntregaMensaje] = field(default_factory=list)
    mensaje_respondido: Optional['Mensaje'] = None

    # Datos del remitente (cargados por el servicio)
    remitente_nombre: Optional[str] = None
    remitente_avatar: Optional[str] = None

    def __post_init__(self):
        """Validaciones al crear el mensaje."""
        if self.contenido and len(self.contenido) > ConstantesChat.MAX_LONGITUD_MENSAJE:
            raise ValueError(
                f"El mensaje excede {ConstantesChat.MAX_LONGITUD_MENSAJE} caracteres"
            )

    @classmethod
    def crear_texto(
        cls,
        conversacion_id: int,
        remitente_id: int,
        contenido: str,
        respuesta_a_id: Optional[int] = None
    ) -> 'Mensaje':
        """Crea un mensaje de texto."""
        return cls(
            id=None,
            public_id=uuid4(),
            conversacion_id=conversacion_id,
            remitente_id=remitente_id,
            contenido=contenido,
            tipo=TipoMensaje.RESPUESTA if respuesta_a_id else TipoMensaje.TEXTO,
            respuesta_a_id=respuesta_a_id,
            creado_en=datetime.now()
        )

    @classmethod
    def crear_sistema(
        cls,
        conversacion_id: int,
        contenido: str,
        remitente_id: int = 1
    ) -> 'Mensaje':
        """Crea un mensaje de sistema.

        remitente_id debe ser un usuario REAL (FK). Por defecto master_admin (1);
        idealmente el actor que dispara el evento (p.ej. el creador del grupo).
        """
        return cls(
            id=None,
            public_id=uuid4(),
            conversacion_id=conversacion_id,
            remitente_id=remitente_id or 1,
            contenido=contenido,
            tipo=TipoMensaje.SISTEMA,
            creado_en=datetime.now()
        )

    @classmethod
    def crear_con_archivos(
        cls,
        conversacion_id: int,
        remitente_id: int,
        tipo_media: TipoMedia,
        contenido: Optional[str] = None
    ) -> 'Mensaje':
        """Crea un mensaje con archivos multimedia."""
        tipo_map = {
            TipoMedia.IMAGEN: TipoMensaje.IMAGEN,
            TipoMedia.VIDEO: TipoMensaje.VIDEO,
            TipoMedia.AUDIO: TipoMensaje.AUDIO,
            TipoMedia.DOCUMENTO: TipoMensaje.DOCUMENTO,
            TipoMedia.STICKER: TipoMensaje.STICKER,
            TipoMedia.GIF: TipoMensaje.GIF,
        }
        return cls(
            id=None,
            public_id=uuid4(),
            conversacion_id=conversacion_id,
            remitente_id=remitente_id,
            contenido=contenido,
            tipo=tipo_map.get(tipo_media, TipoMensaje.DOCUMENTO),
            creado_en=datetime.now()
        )

    @classmethod
    def crear_ubicacion(
        cls,
        conversacion_id: int,
        remitente_id: int,
        ubicacion: UbicacionMensaje
    ) -> 'Mensaje':
        """Crea un mensaje con ubicacion."""
        return cls(
            id=None,
            public_id=uuid4(),
            conversacion_id=conversacion_id,
            remitente_id=remitente_id,
            contenido=ubicacion.nombre or ubicacion.direccion,
            tipo=TipoMensaje.UBICACION,
            metadata=ubicacion.to_dict(),
            creado_en=datetime.now()
        )

    @classmethod
    def crear_contacto(
        cls,
        conversacion_id: int,
        remitente_id: int,
        contacto: ContactoMensaje
    ) -> 'Mensaje':
        """Crea un mensaje con contacto."""
        return cls(
            id=None,
            public_id=uuid4(),
            conversacion_id=conversacion_id,
            remitente_id=remitente_id,
            contenido=contacto.nombre,
            tipo=TipoMensaje.CONTACTO,
            metadata=contacto.to_dict(),
            creado_en=datetime.now()
        )

    @classmethod
    def crear_gif(
        cls,
        conversacion_id: int,
        remitente_id: int,
        url_gif: str,
        contenido: Optional[str] = None
    ) -> 'Mensaje':
        """Crea un mensaje con GIF."""
        return cls(
            id=None,
            public_id=uuid4(),
            conversacion_id=conversacion_id,
            remitente_id=remitente_id,
            contenido=contenido,
            tipo=TipoMensaje.GIF,
            metadata={'gif_url': url_gif},
            creado_en=datetime.now()
        )

    def es_de_sistema(self) -> bool:
        """Verifica si es un mensaje de sistema."""
        return self.tipo == TipoMensaje.SISTEMA

    def es_texto(self) -> bool:
        """Verifica si es un mensaje de texto simple."""
        return self.tipo == TipoMensaje.TEXTO

    def tiene_archivos(self) -> bool:
        """Verifica si tiene archivos adjuntos."""
        return len(self.archivos) > 0

    def es_respuesta(self) -> bool:
        """Verifica si es una respuesta a otro mensaje."""
        return self.respuesta_a_id is not None

    def es_reenviado(self) -> bool:
        """Verifica si es un mensaje reenviado."""
        return self.reenviado_de_id is not None

    def es_ubicacion(self) -> bool:
        """Verifica si es un mensaje de ubicacion."""
        return self.tipo == TipoMensaje.UBICACION

    def es_contacto(self) -> bool:
        """Verifica si es un mensaje de contacto."""
        return self.tipo == TipoMensaje.CONTACTO

    def es_gif(self) -> bool:
        """Verifica si es un mensaje GIF."""
        return self.tipo == TipoMensaje.GIF

    def obtener_ubicacion(self) -> Optional[Dict[str, Any]]:
        """Obtiene los datos de ubicacion si es mensaje de ubicacion."""
        if self.es_ubicacion():
            return self.metadata
        return None

    def obtener_contacto(self) -> Optional[Dict[str, Any]]:
        """Obtiene los datos del contacto si es mensaje de contacto."""
        if self.es_contacto():
            return self.metadata
        return None

    def puede_editar(self, usuario_id: int) -> bool:
        """Verifica si el usuario puede editar este mensaje."""
        if self.remitente_id != usuario_id:
            return False
        if self.eliminado:
            return False
        if self.es_de_sistema():
            return False
        if not self.creado_en:
            return False

        ahora = datetime.now(timezone.utc) if self.creado_en.tzinfo else datetime.now()
        tiempo_transcurrido = (ahora - self.creado_en).total_seconds()
        return tiempo_transcurrido < ConstantesChat.TIEMPO_EDITAR_MENSAJE

    def puede_eliminar(self, usuario_id: int, es_moderador: bool = False) -> bool:
        """Verifica si el usuario puede eliminar este mensaje."""
        if self.eliminado:
            return False
        if self.es_de_sistema():
            return False

        # Moderadores pueden eliminar cualquier mensaje
        if es_moderador:
            return True

        # El remitente puede eliminar dentro del tiempo limite
        if self.remitente_id == usuario_id:
            if not self.creado_en:
                return False
            ahora = datetime.now(timezone.utc) if self.creado_en.tzinfo else datetime.now()
            tiempo_transcurrido = (ahora - self.creado_en).total_seconds()
            return tiempo_transcurrido < ConstantesChat.TIEMPO_ELIMINAR_MENSAJE

        return False

    def editar(self, nuevo_contenido: str):
        """Edita el contenido del mensaje."""
        if len(nuevo_contenido) > ConstantesChat.MAX_LONGITUD_MENSAJE:
            raise ValueError(
                f"El mensaje excede {ConstantesChat.MAX_LONGITUD_MENSAJE} caracteres"
            )
        self.contenido = nuevo_contenido
        self.editado = True
        self.actualizado_en = datetime.now()

    def eliminar(self, para_todos: bool = False):
        """Marca el mensaje como eliminado."""
        self.eliminado = True
        self.eliminado_en = datetime.now()
        self.eliminado_para_todos = para_todos
        if para_todos:
            self.contenido = None
            self.archivos = []

    def obtener_reacciones_agrupadas(self) -> Dict[str, List[int]]:
        """Agrupa las reacciones por emoji."""
        agrupadas: Dict[str, List[int]] = {}
        for reaccion in self.reacciones:
            if reaccion.emoji not in agrupadas:
                agrupadas[reaccion.emoji] = []
            agrupadas[reaccion.emoji].append(reaccion.usuario_id)
        return agrupadas

    def estado_global(self) -> EstadoMensaje:
        """Obtiene el estado global del mensaje (el minimo de todos los destinatarios)."""
        if not self.estados_entrega:
            return EstadoMensaje.ENVIADO

        todos_leidos = all(e.leido for e in self.estados_entrega)
        if todos_leidos:
            return EstadoMensaje.LEIDO

        todos_entregados = all(e.entregado for e in self.estados_entrega)
        if todos_entregados:
            return EstadoMensaje.ENTREGADO

        return EstadoMensaje.ENVIADO

    def to_dict(self, incluir_remitente: bool = True) -> Dict[str, Any]:
        """Convierte la entidad a diccionario."""
        data = {
            'id': self.id,
            'public_id': str(self.public_id),
            'conversacion_id': self.conversacion_id,
            'remitente_id': self.remitente_id,
            'contenido': self.contenido if not self.eliminado else None,
            'tipo': self.tipo.value,
            'respuesta_a_id': self.respuesta_a_id,
            'forwarded_from_id': self.reenviado_de_id,
            'message_type': self.tipo.value,
            'editado': self.editado,
            'eliminado': self.eliminado,
            'eliminado_para_todos': self.eliminado_para_todos,
            'archivos': [a.to_dict() for a in self.archivos],
            'reacciones': self.obtener_reacciones_agrupadas(),
            'estado': self.estado_global().value,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
            'actualizado_en': self.actualizado_en.isoformat() if self.actualizado_en else None,
        }

        if incluir_remitente:
            data['remitente'] = {
                'id': self.remitente_id,
                'nombre': self.remitente_nombre,
                'avatar': self.remitente_avatar,
            }

        if self.mensaje_respondido:
            data['mensaje_respondido'] = {
                'id': self.mensaje_respondido.id,
                'contenido': self.mensaje_respondido.contenido[:100] if self.mensaje_respondido.contenido else None,
                'remitente_nombre': self.mensaje_respondido.remitente_nombre,
            }

        # Incluir datos especiales segun tipo de mensaje
        if self.es_ubicacion() and self.metadata:
            data['ubicacion'] = self.metadata
        elif self.es_contacto() and self.metadata:
            data['contacto'] = self.metadata
        elif self.es_gif() and self.metadata:
            data['gif_url'] = self.metadata.get('gif_url')

        return data
