# -*- coding: utf-8 -*-
"""
Value Objects: Tipos del Chat Institucional

Enums y value objects para el sistema de chat.

CAPA: modulos/chat/dominio/value_objects
ARQUITECTURA: Hexagonal - 100%

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado: 2026-01-05
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class TipoConversacion(Enum):
    """Tipo de conversacion."""
    DIRECTA = "direct"
    GRUPO = "group"
    IA = "ia"  # Conversacion con IA Maquita


class TipoMensaje(Enum):
    """Tipo de mensaje."""
    TEXTO = "text"
    IMAGEN = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENTO = "document"
    STICKER = "sticker"
    GIF = "gif"
    UBICACION = "location"
    CONTACTO = "contact"
    SISTEMA = "system"
    RESPUESTA = "reply"
    REENVIADO = "forwarded"
    IA_RESPUESTA = "ia_response"  # Respuesta de IA Maquita
    IA_PENSANDO = "ia_thinking"   # Indicador de que IA esta procesando


class RolParticipante(Enum):
    """Rol del participante en una conversacion."""
    ADMIN = "admin"
    MODERADOR = "moderator"
    MIEMBRO = "member"


class EstadoMensaje(Enum):
    """Estado de entrega del mensaje."""
    ENVIADO = "sent"
    ENTREGADO = "delivered"
    LEIDO = "read"


class TipoMedia(Enum):
    """Tipo de archivo multimedia."""
    IMAGEN = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENTO = "document"
    STICKER = "sticker"
    GIF = "gif"


class EstadoPresencia(Enum):
    """Estado de presencia del usuario."""
    EN_LINEA = "online"
    AUSENTE = "away"
    DESCONECTADO = "offline"


class AccionUsuario(Enum):
    """Accion que esta realizando el usuario en el chat."""
    ESCRIBIENDO = "typing"
    GRABANDO_AUDIO = "recording_audio"
    GRABANDO_VIDEO = "recording_video"
    SUBIENDO_ARCHIVO = "uploading"
    TOMANDO_FOTO = "taking_photo"
    ELIGIENDO_STICKER = "choosing_sticker"
    NINGUNA = "none"


# =============================================================================
# CONSTANTES DEL CHAT
# =============================================================================

class ConstantesChat:
    """Constantes de configuracion del chat."""

    # Limites de tamaño de archivo (bytes)
    MAX_IMAGEN_SIZE = 10 * 1024 * 1024      # 10 MB
    MAX_VIDEO_SIZE = 50 * 1024 * 1024       # 50 MB
    MAX_AUDIO_SIZE = 20 * 1024 * 1024       # 20 MB
    MAX_DOCUMENTO_SIZE = 25 * 1024 * 1024   # 25 MB

    # Limites de contenido
    MAX_LONGITUD_MENSAJE = 4000             # caracteres
    MAX_NOMBRE_GRUPO = 100                  # caracteres
    MAX_DESCRIPCION_GRUPO = 500             # caracteres
    MAX_PARTICIPANTES_GRUPO = 256           # usuarios
    MAX_ARCHIVOS_POR_MENSAJE = 10           # archivos

    # Tiempos
    TIMEOUT_ESCRIBIENDO = 10                # segundos
    TIEMPO_EDITAR_MENSAJE = 30 * 60         # 30 minutos en segundos
    TIEMPO_ELIMINAR_MENSAJE = 60 * 60       # 60 minutos en segundos

    # Paginacion
    MENSAJES_POR_PAGINA = 50
    MAX_MENSAJES_POR_PAGINA = 100
    CONVERSACIONES_POR_PAGINA = 20

    # Extensiones permitidas
    EXTENSIONES_IMAGEN = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    EXTENSIONES_VIDEO = {'mp4', 'webm', 'mov', 'avi'}
    EXTENSIONES_AUDIO = {'mp3', 'wav', 'ogg', 'm4a', 'opus'}
    EXTENSIONES_DOCUMENTO = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'zip', 'rar'}
    EXTENSIONES_GIF = {'gif'}

    # IA Maquita - Configuracion
    IA_MAQUITA_NOMBRE = "IA Maquita"
    IA_MAQUITA_AVATAR = "/static/img/ia-maquita-avatar.png"
    IA_MAQUITA_MODELO = "llama3.2:3b"
    IA_TIMEOUT_RESPUESTA = 120               # segundos para esperar respuesta
    IA_MAX_HISTORIAL = 20                    # mensajes de contexto
    IA_MAX_TOKENS_RESPUESTA = 2048           # tokens maximos en respuesta


# =============================================================================
# ENUMS PARA IA
# =============================================================================

class CapacidadIA(Enum):
    """Capacidades disponibles de IA Maquita."""
    CHAT = "chat"                    # Chat conversacional
    TRANSCRIPCION = "transcription"  # Transcripcion de audio (Whisper)
    DOCUMENTOS = "documents"         # Analisis de documentos
    RESUMEN = "summary"              # Resumen de textos
    TRADUCCION = "translation"       # Traduccion
    ASISTENTE = "assistant"          # Asistente general


class EstadoIA(Enum):
    """Estado de la conexion con IA."""
    DISPONIBLE = "available"
    OCUPADO = "busy"
    DESCONECTADO = "offline"
    ERROR = "error"


# =============================================================================
# VALUE OBJECTS
# =============================================================================

@dataclass(frozen=True)
class ContenidoMensaje:
    """Value object para el contenido de un mensaje."""
    texto: str

    def __post_init__(self):
        if len(self.texto) > ConstantesChat.MAX_LONGITUD_MENSAJE:
            raise ValueError(
                f"El mensaje excede el limite de {ConstantesChat.MAX_LONGITUD_MENSAJE} caracteres"
            )

    @property
    def es_vacio(self) -> bool:
        return not self.texto or not self.texto.strip()

    @property
    def longitud(self) -> int:
        return len(self.texto)


@dataclass(frozen=True)
class InfoArchivo:
    """Value object para informacion de archivo multimedia."""
    nombre: str
    ruta: str
    tipo_mime: str
    tamanio: int
    tipo: TipoMedia
    ancho: Optional[int] = None
    alto: Optional[int] = None
    duracion: Optional[int] = None  # segundos para audio/video
    ruta_miniatura: Optional[str] = None

    def __post_init__(self):
        # Validar tamanio segun tipo
        limites = {
            TipoMedia.IMAGEN: ConstantesChat.MAX_IMAGEN_SIZE,
            TipoMedia.VIDEO: ConstantesChat.MAX_VIDEO_SIZE,
            TipoMedia.AUDIO: ConstantesChat.MAX_AUDIO_SIZE,
            TipoMedia.DOCUMENTO: ConstantesChat.MAX_DOCUMENTO_SIZE,
            TipoMedia.STICKER: ConstantesChat.MAX_IMAGEN_SIZE,
        }
        limite = limites.get(self.tipo, ConstantesChat.MAX_DOCUMENTO_SIZE)
        if self.tamanio > limite:
            raise ValueError(f"El archivo excede el limite de {limite // (1024*1024)} MB")


@dataclass(frozen=True)
class IndicadorEscritura:
    """Value object para indicador de escritura."""
    usuario_id: int
    conversacion_id: int
    inicio: datetime

    def esta_activo(self) -> bool:
        """Verifica si el indicador sigue activo (menos de 10 segundos)."""
        diferencia = (datetime.now() - self.inicio).total_seconds()
        return diferencia < ConstantesChat.TIMEOUT_ESCRIBIENDO


@dataclass(frozen=True)
class PresenciaUsuario:
    """Value object para presencia de usuario."""
    usuario_id: int
    en_linea: bool
    ultima_vez: datetime

    @property
    def estado(self) -> EstadoPresencia:
        if self.en_linea:
            return EstadoPresencia.EN_LINEA
        return EstadoPresencia.DESCONECTADO

    @property
    def texto_ultima_vez(self) -> str:
        """Retorna texto legible de ultima conexion."""
        if self.en_linea:
            return "En linea"

        ahora = datetime.now()
        diferencia = ahora - self.ultima_vez

        if diferencia.days > 0:
            if diferencia.days == 1:
                return "Ayer"
            return f"Hace {diferencia.days} dias"

        horas = diferencia.seconds // 3600
        if horas > 0:
            return f"Hace {horas} hora{'s' if horas > 1 else ''}"

        minutos = diferencia.seconds // 60
        if minutos > 0:
            return f"Hace {minutos} minuto{'s' if minutos > 1 else ''}"

        return "Hace un momento"


@dataclass(frozen=True)
class UbicacionMensaje:
    """Value object para ubicacion compartida en mensaje."""
    latitud: float
    longitud: float
    nombre: Optional[str] = None  # Nombre del lugar
    direccion: Optional[str] = None  # Direccion formateada

    def __post_init__(self):
        if not -90 <= self.latitud <= 90:
            raise ValueError("Latitud debe estar entre -90 y 90")
        if not -180 <= self.longitud <= 180:
            raise ValueError("Longitud debe estar entre -180 y 180")

    @property
    def url_mapa(self) -> str:
        """Genera URL de Google Maps para la ubicacion."""
        return f"https://www.google.com/maps?q={self.latitud},{self.longitud}"

    def to_dict(self) -> dict:
        return {
            'latitud': self.latitud,
            'longitud': self.longitud,
            'nombre': self.nombre,
            'direccion': self.direccion,
            'url_mapa': self.url_mapa
        }


@dataclass(frozen=True)
class ContactoMensaje:
    """Value object para contacto compartido en mensaje."""
    nombre: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    organizacion: Optional[str] = None
    cargo: Optional[str] = None
    notas: Optional[str] = None

    def __post_init__(self):
        if not self.nombre or not self.nombre.strip():
            raise ValueError("El nombre del contacto es requerido")
        if not self.telefono and not self.email:
            raise ValueError("Se requiere al menos telefono o email")

    def to_dict(self) -> dict:
        return {
            'nombre': self.nombre,
            'telefono': self.telefono,
            'email': self.email,
            'organizacion': self.organizacion,
            'cargo': self.cargo,
            'notas': self.notas
        }
