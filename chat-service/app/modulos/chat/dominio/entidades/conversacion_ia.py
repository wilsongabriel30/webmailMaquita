# -*- coding: utf-8 -*-
"""
Entidad de Dominio: ConversacionIA

Representa una conversacion con IA Maquita.
Extiende el concepto de conversacion para interactuar con el asistente de IA.

CAPA: modulos/chat/dominio/entidades
ARQUITECTURA: Hexagonal - 100%

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-06
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from modulos.chat.dominio.value_objects.tipos_chat import (
    TipoConversacion,
    TipoMensaje,
    CapacidadIA,
    EstadoIA,
    ConstantesChat
)


# ID especial para IA Maquita (usuario virtual)
IA_MAQUITA_USER_ID = -1


@dataclass
class MensajeIA:
    """
    Entidad que representa un mensaje en una conversacion con IA.

    Incluye metadatos especificos de IA como tokens usados,
    modelo utilizado, tiempo de respuesta, etc.
    """
    id: Optional[int]
    public_id: UUID
    conversacion_ia_id: int
    es_usuario: bool  # True = mensaje del usuario, False = respuesta IA
    contenido: str
    tipo: TipoMensaje

    # Metadatos de IA (solo para respuestas de IA)
    modelo: Optional[str] = None
    tokens_prompt: Optional[int] = None
    tokens_respuesta: Optional[int] = None
    tiempo_respuesta_ms: Optional[int] = None
    capacidad_usada: Optional[CapacidadIA] = None

    # Metadatos generales
    metadata: Dict[str, Any] = field(default_factory=dict)
    creado_en: Optional[datetime] = None

    @classmethod
    def crear_mensaje_usuario(
        cls,
        conversacion_ia_id: int,
        contenido: str
    ) -> 'MensajeIA':
        """Crea un mensaje del usuario para la IA."""
        return cls(
            id=None,
            public_id=uuid4(),
            conversacion_ia_id=conversacion_ia_id,
            es_usuario=True,
            contenido=contenido,
            tipo=TipoMensaje.TEXTO,
            creado_en=datetime.now()
        )

    @classmethod
    def crear_respuesta_ia(
        cls,
        conversacion_ia_id: int,
        contenido: str,
        modelo: str,
        tokens_prompt: int = 0,
        tokens_respuesta: int = 0,
        tiempo_respuesta_ms: int = 0,
        capacidad: CapacidadIA = CapacidadIA.CHAT
    ) -> 'MensajeIA':
        """Crea una respuesta de IA Maquita."""
        return cls(
            id=None,
            public_id=uuid4(),
            conversacion_ia_id=conversacion_ia_id,
            es_usuario=False,
            contenido=contenido,
            tipo=TipoMensaje.IA_RESPUESTA,
            modelo=modelo,
            tokens_prompt=tokens_prompt,
            tokens_respuesta=tokens_respuesta,
            tiempo_respuesta_ms=tiempo_respuesta_ms,
            capacidad_usada=capacidad,
            creado_en=datetime.now()
        )

    @classmethod
    def crear_indicador_pensando(cls, conversacion_ia_id: int) -> 'MensajeIA':
        """Crea un mensaje indicador de que IA esta procesando."""
        return cls(
            id=None,
            public_id=uuid4(),
            conversacion_ia_id=conversacion_ia_id,
            es_usuario=False,
            contenido="",
            tipo=TipoMensaje.IA_PENSANDO,
            creado_en=datetime.now()
        )

    def es_respuesta_ia(self) -> bool:
        """Verifica si es una respuesta de IA."""
        return not self.es_usuario

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la entidad a diccionario."""
        data = {
            'id': self.id,
            'public_id': str(self.public_id),
            'conversacion_ia_id': self.conversacion_ia_id,
            'es_usuario': self.es_usuario,
            'contenido': self.contenido,
            'tipo': self.tipo.value,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
        }

        # Agregar metadatos de IA solo si es respuesta
        if not self.es_usuario:
            data['ia_metadata'] = {
                'modelo': self.modelo,
                'tokens_prompt': self.tokens_prompt,
                'tokens_respuesta': self.tokens_respuesta,
                'tiempo_respuesta_ms': self.tiempo_respuesta_ms,
                'capacidad_usada': self.capacidad_usada.value if self.capacidad_usada else None,
            }

        return data


@dataclass
class ConversacionIA:
    """
    Entidad que representa una conversacion con IA Maquita.

    Cada usuario tiene una conversacion unica con IA Maquita,
    similar a como funciona un asistente de IA.
    """
    id: Optional[int]
    public_id: UUID
    usuario_id: int  # Usuario que conversa con IA
    titulo: Optional[str] = None  # Titulo generado automaticamente o por usuario

    # Estado de la conversacion
    activa: bool = True
    archivada: bool = False

    # Configuracion de IA para esta conversacion
    modelo_preferido: str = ConstantesChat.IA_MAQUITA_MODELO
    contexto_sistema: Optional[str] = None  # Prompt de sistema personalizado
    temperatura: float = 0.7  # Creatividad de respuestas (0-1)

    # Estadisticas
    total_mensajes: int = 0
    tokens_totales: int = 0

    # Timestamps
    ultimo_mensaje_en: Optional[datetime] = None
    creada_en: Optional[datetime] = None
    actualizada_en: Optional[datetime] = None

    # Mensajes (cargados por el repositorio)
    mensajes: List[MensajeIA] = field(default_factory=list)

    @classmethod
    def crear_nueva(cls, usuario_id: int, titulo: Optional[str] = None) -> 'ConversacionIA':
        """Crea una nueva conversacion con IA Maquita."""
        return cls(
            id=None,
            public_id=uuid4(),
            usuario_id=usuario_id,
            titulo=titulo or "Nueva conversacion con IA Maquita",
            creada_en=datetime.now()
        )

    def agregar_mensaje_usuario(self, contenido: str) -> MensajeIA:
        """Agrega un mensaje del usuario a la conversacion."""
        mensaje = MensajeIA.crear_mensaje_usuario(
            conversacion_ia_id=self.id,
            contenido=contenido
        )
        self.mensajes.append(mensaje)
        self.total_mensajes += 1
        self.ultimo_mensaje_en = datetime.now()
        self.actualizada_en = datetime.now()
        return mensaje

    def agregar_respuesta_ia(
        self,
        contenido: str,
        modelo: str,
        tokens_prompt: int = 0,
        tokens_respuesta: int = 0,
        tiempo_respuesta_ms: int = 0,
        capacidad: CapacidadIA = CapacidadIA.CHAT
    ) -> MensajeIA:
        """Agrega una respuesta de IA a la conversacion."""
        mensaje = MensajeIA.crear_respuesta_ia(
            conversacion_ia_id=self.id,
            contenido=contenido,
            modelo=modelo,
            tokens_prompt=tokens_prompt,
            tokens_respuesta=tokens_respuesta,
            tiempo_respuesta_ms=tiempo_respuesta_ms,
            capacidad=capacidad
        )
        self.mensajes.append(mensaje)
        self.total_mensajes += 1
        self.tokens_totales += tokens_prompt + tokens_respuesta
        self.ultimo_mensaje_en = datetime.now()
        self.actualizada_en = datetime.now()
        return mensaje

    def obtener_historial_contexto(self, limite: int = None) -> List[Dict[str, str]]:
        """
        Obtiene el historial de mensajes en formato para el modelo LLM.

        Returns:
            Lista de diccionarios con 'role' y 'content' para cada mensaje
        """
        limite = limite or ConstantesChat.IA_MAX_HISTORIAL
        mensajes_recientes = self.mensajes[-limite:] if len(self.mensajes) > limite else self.mensajes

        historial = []
        for msg in mensajes_recientes:
            if msg.tipo == TipoMensaje.IA_PENSANDO:
                continue
            historial.append({
                'role': 'user' if msg.es_usuario else 'assistant',
                'content': msg.contenido
            })

        return historial

    def generar_titulo_automatico(self) -> str:
        """Genera un titulo basado en el primer mensaje del usuario."""
        for msg in self.mensajes:
            if msg.es_usuario and msg.contenido:
                # Tomar las primeras palabras del primer mensaje
                palabras = msg.contenido.split()[:6]
                titulo = ' '.join(palabras)
                if len(titulo) > 50:
                    titulo = titulo[:47] + '...'
                return titulo
        return "Nueva conversacion"

    def archivar(self):
        """Archiva la conversacion."""
        self.archivada = True
        self.actualizada_en = datetime.now()

    def desarchivar(self):
        """Desarchiva la conversacion."""
        self.archivada = False
        self.actualizada_en = datetime.now()

    def to_dict(self, incluir_mensajes: bool = False) -> Dict[str, Any]:
        """Convierte la entidad a diccionario."""
        data = {
            'id': self.id,
            'public_id': str(self.public_id),
            'usuario_id': self.usuario_id,
            'titulo': self.titulo,
            'activa': self.activa,
            'archivada': self.archivada,
            'modelo_preferido': self.modelo_preferido,
            'total_mensajes': self.total_mensajes,
            'tokens_totales': self.tokens_totales,
            'ultimo_mensaje_en': self.ultimo_mensaje_en.isoformat() if self.ultimo_mensaje_en else None,
            'creada_en': self.creada_en.isoformat() if self.creada_en else None,
            # Datos de IA Maquita como contacto virtual
            'ia_contacto': {
                'nombre': ConstantesChat.IA_MAQUITA_NOMBRE,
                'avatar': ConstantesChat.IA_MAQUITA_AVATAR,
                'usuario_id': IA_MAQUITA_USER_ID,
            }
        }

        if incluir_mensajes:
            data['mensajes'] = [m.to_dict() for m in self.mensajes]

        return data

    def to_lista_conversaciones(self) -> Dict[str, Any]:
        """
        Formato para mostrar en lista de conversaciones del chat.
        Compatible con el formato de Conversacion normal.
        """
        ultimo_mensaje = self.mensajes[-1] if self.mensajes else None
        return {
            'id': self.id,
            'public_id': str(self.public_id),
            'tipo': TipoConversacion.IA.value,
            'nombre': ConstantesChat.IA_MAQUITA_NOMBRE,
            'avatar_ruta': ConstantesChat.IA_MAQUITA_AVATAR,
            'ultimo_mensaje_en': self.ultimo_mensaje_en.isoformat() if self.ultimo_mensaje_en else None,
            'ultimo_mensaje_preview': ultimo_mensaje.contenido[:100] if ultimo_mensaje else None,
            'mensajes_no_leidos': 0,  # IA siempre responde inmediatamente
            'es_ia': True,
            'subtitulo': self.titulo,
        }


@dataclass
class ConfiguracionIAUsuario:
    """
    Configuracion de IA para un usuario especifico.
    Permite personalizar la experiencia de cada usuario con IA Maquita.
    """
    id: Optional[int]
    usuario_id: int

    # Preferencias de modelo
    modelo_preferido: str = ConstantesChat.IA_MAQUITA_MODELO
    temperatura: float = 0.7

    # Limites
    max_tokens_por_respuesta: int = ConstantesChat.IA_MAX_TOKENS_RESPUESTA
    max_mensajes_por_dia: int = 100

    # Contadores de uso
    mensajes_hoy: int = 0
    tokens_usados_hoy: int = 0
    ultimo_reset: Optional[datetime] = None

    # Estado
    habilitado: bool = True

    creado_en: Optional[datetime] = None
    actualizado_en: Optional[datetime] = None

    def puede_enviar_mensaje(self) -> bool:
        """Verifica si el usuario puede enviar mas mensajes."""
        if not self.habilitado:
            return False
        return self.mensajes_hoy < self.max_mensajes_por_dia

    def registrar_uso(self, tokens: int):
        """Registra el uso de tokens."""
        self.mensajes_hoy += 1
        self.tokens_usados_hoy += tokens
        self.actualizado_en = datetime.now()

    def reset_diario(self):
        """Resetea los contadores diarios."""
        self.mensajes_hoy = 0
        self.tokens_usados_hoy = 0
        self.ultimo_reset = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'usuario_id': self.usuario_id,
            'modelo_preferido': self.modelo_preferido,
            'temperatura': self.temperatura,
            'max_tokens_por_respuesta': self.max_tokens_por_respuesta,
            'max_mensajes_por_dia': self.max_mensajes_por_dia,
            'mensajes_hoy': self.mensajes_hoy,
            'tokens_usados_hoy': self.tokens_usados_hoy,
            'habilitado': self.habilitado,
            'puede_enviar': self.puede_enviar_mensaje(),
        }
