# -*- coding: utf-8 -*-
"""
Entidad de Dominio: Conversacion

Representa una conversacion de chat (directa o grupal).

CAPA: modulos/chat/dominio/entidades
ARQUITECTURA: Hexagonal - 100%

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado: 2026-01-05
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from modulos.chat.dominio.value_objects.tipos_chat import (
    TipoConversacion,
    RolParticipante,
    ConstantesChat
)


@dataclass
class Participante:
    """
    Entidad que representa un participante en una conversacion.
    """
    id: Optional[int]
    conversacion_id: int
    usuario_id: int
    rol: RolParticipante
    apodo: Optional[str] = None
    silenciado: bool = False
    silenciado_hasta: Optional[datetime] = None
    activo: bool = True
    ultimo_mensaje_leido_id: Optional[int] = None
    ultimo_leido_en: Optional[datetime] = None
    mensajes_no_leidos: int = 0
    unido_en: Optional[datetime] = None

    def es_admin(self) -> bool:
        """Verifica si el participante es administrador."""
        return self.rol == RolParticipante.ADMIN

    def es_moderador(self) -> bool:
        """Verifica si el participante es moderador o superior."""
        return self.rol in (RolParticipante.ADMIN, RolParticipante.MODERADOR)

    def puede_eliminar_mensajes(self) -> bool:
        """Verifica si puede eliminar mensajes de otros."""
        return self.es_moderador()

    def puede_agregar_miembros(self) -> bool:
        """Verifica si puede agregar miembros al grupo."""
        return self.es_moderador()

    def puede_expulsar_miembros(self) -> bool:
        """Verifica si puede expulsar miembros."""
        return self.es_admin()

    def esta_silenciado(self) -> bool:
        """Verifica si el participante esta silenciado."""
        if not self.silenciado:
            return False
        if self.silenciado_hasta and self.silenciado_hasta < datetime.now():
            return False
        return True


@dataclass
class Conversacion:
    """
    Entidad que representa una conversacion de chat.

    Puede ser:
    - Directa (1:1): Entre dos usuarios
    - Grupo: Multiples usuarios con nombre y descripcion
    """
    id: Optional[int]
    public_id: UUID
    tipo: TipoConversacion
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    avatar_ruta: Optional[str] = None
    creador_id: Optional[int] = None
    ultimo_mensaje_en: Optional[datetime] = None
    ultimo_mensaje_preview: Optional[str] = None
    activa: bool = True
    configuracion: Dict[str, Any] = field(default_factory=dict)
    creada_en: Optional[datetime] = None
    actualizada_en: Optional[datetime] = None

    # Participantes (cargados por el repositorio)
    participantes: List[Participante] = field(default_factory=list)

    def __post_init__(self):
        """Validaciones al crear la conversacion."""
        if self.tipo == TipoConversacion.GRUPO:
            if not self.nombre:
                raise ValueError("Los grupos deben tener un nombre")
            if len(self.nombre) > ConstantesChat.MAX_NOMBRE_GRUPO:
                raise ValueError(
                    f"El nombre del grupo excede {ConstantesChat.MAX_NOMBRE_GRUPO} caracteres"
                )
            if self.descripcion and len(self.descripcion) > ConstantesChat.MAX_DESCRIPCION_GRUPO:
                raise ValueError(
                    f"La descripcion excede {ConstantesChat.MAX_DESCRIPCION_GRUPO} caracteres"
                )

    @classmethod
    def crear_directa(cls, usuario1_id: int, usuario2_id: int) -> 'Conversacion':
        """
        Crea una conversacion directa entre dos usuarios.
        """
        conversacion = cls(
            id=None,
            public_id=uuid4(),
            tipo=TipoConversacion.DIRECTA,
            creada_en=datetime.now()
        )
        # Los participantes se agregan por el servicio
        return conversacion

    @classmethod
    def crear_grupo(
        cls,
        nombre: str,
        creador_id: int,
        descripcion: Optional[str] = None
    ) -> 'Conversacion':
        """
        Crea una conversacion grupal.
        """
        return cls(
            id=None,
            public_id=uuid4(),
            tipo=TipoConversacion.GRUPO,
            nombre=nombre,
            descripcion=descripcion,
            creador_id=creador_id,
            creada_en=datetime.now()
        )

    def es_directa(self) -> bool:
        """Verifica si es una conversacion directa."""
        return self.tipo == TipoConversacion.DIRECTA

    def es_grupo(self) -> bool:
        """Verifica si es un grupo."""
        return self.tipo == TipoConversacion.GRUPO

    def obtener_participante(self, usuario_id: int) -> Optional[Participante]:
        """Obtiene un participante por su usuario_id."""
        for p in self.participantes:
            if p.usuario_id == usuario_id and p.activo:
                return p
        return None

    def es_participante(self, usuario_id: int) -> bool:
        """Verifica si un usuario es participante activo."""
        return self.obtener_participante(usuario_id) is not None

    def obtener_admins(self) -> List[Participante]:
        """Obtiene la lista de administradores."""
        return [p for p in self.participantes if p.es_admin() and p.activo]

    def contar_participantes_activos(self) -> int:
        """Cuenta los participantes activos."""
        return len([p for p in self.participantes if p.activo])

    def puede_agregar_participantes(self) -> bool:
        """Verifica si se pueden agregar mas participantes."""
        if self.es_directa():
            return False
        return self.contar_participantes_activos() < ConstantesChat.MAX_PARTICIPANTES_GRUPO

    def obtener_otro_participante(self, usuario_id: int) -> Optional[Participante]:
        """
        En conversaciones directas, obtiene el otro participante.
        """
        if not self.es_directa():
            return None
        for p in self.participantes:
            if p.usuario_id != usuario_id and p.activo:
                return p
        return None

    def actualizar_ultimo_mensaje(self, contenido: str, fecha: datetime):
        """Actualiza la informacion del ultimo mensaje."""
        self.ultimo_mensaje_en = fecha
        # Truncar preview a 100 caracteres
        self.ultimo_mensaje_preview = contenido[:100] if contenido else None
        self.actualizada_en = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la entidad a diccionario."""
        return {
            'id': self.id,
            'public_id': str(self.public_id),
            'tipo': self.tipo.value,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'avatar_ruta': self.avatar_ruta,
            'creador_id': self.creador_id,
            'ultimo_mensaje_en': self.ultimo_mensaje_en.isoformat() if self.ultimo_mensaje_en else None,
            'ultimo_mensaje_preview': self.ultimo_mensaje_preview,
            'activa': self.activa,
            'participantes_count': self.contar_participantes_activos(),
            'creada_en': self.creada_en.isoformat() if self.creada_en else None,
        }
