# -*- coding: utf-8 -*-
"""
Value Objects: Permisos de documentos PDF.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class NivelAcceso(str, Enum):
    """Niveles de acceso a un documento."""
    LECTOR = 'lector'           # Solo puede ver
    COMENTADOR = 'comentador'   # Puede ver y comentar
    EDITOR = 'editor'           # Puede ver, comentar y editar
    FIRMANTE = 'firmante'       # Puede ver y firmar
    PROPIETARIO = 'propietario' # Acceso total


@dataclass
class PermisoUsuario:
    """
    Permiso individual para un usuario.
    """

    usuario_id: int
    nivel: NivelAcceso
    fecha_expiracion: Optional[datetime] = None
    notificar_cambios: bool = False

    @property
    def esta_vigente(self) -> bool:
        """Verifica si el permiso está vigente."""
        if self.fecha_expiracion is None:
            return True
        return datetime.now() < self.fecha_expiracion

    def puede_ver(self) -> bool:
        """Verifica si puede ver el documento."""
        return self.esta_vigente

    def puede_comentar(self) -> bool:
        """Verifica si puede comentar."""
        return self.esta_vigente and self.nivel in (
            NivelAcceso.COMENTADOR,
            NivelAcceso.EDITOR,
            NivelAcceso.PROPIETARIO
        )

    def puede_editar(self) -> bool:
        """Verifica si puede editar."""
        return self.esta_vigente and self.nivel in (
            NivelAcceso.EDITOR,
            NivelAcceso.PROPIETARIO
        )

    def puede_firmar(self) -> bool:
        """Verifica si puede firmar."""
        return self.esta_vigente and self.nivel in (
            NivelAcceso.FIRMANTE,
            NivelAcceso.EDITOR,
            NivelAcceso.PROPIETARIO
        )

    def puede_eliminar(self) -> bool:
        """Verifica si puede eliminar."""
        return self.esta_vigente and self.nivel == NivelAcceso.PROPIETARIO

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'usuario_id': self.usuario_id,
            'nivel': self.nivel.value,
            'fecha_expiracion': self.fecha_expiracion.isoformat() if self.fecha_expiracion else None,
            'notificar_cambios': self.notificar_cambios
        }


@dataclass
class PermisoDocumento:
    """
    Configuración completa de permisos de un documento.
    """

    publico: bool = False
    requiere_contrasena: bool = False
    contrasena_hash: Optional[str] = None
    permite_descarga: bool = True
    permite_impresion: bool = True
    permite_copia: bool = True
    fecha_expiracion_publica: Optional[datetime] = None
    usuarios: List[PermisoUsuario] = field(default_factory=list)
    enlace_compartido: Optional[str] = None

    def agregar_usuario(
        self,
        usuario_id: int,
        nivel: NivelAcceso,
        fecha_expiracion: datetime = None
    ) -> None:
        """Agrega un usuario con permisos."""
        # Remover permiso existente si hay
        self.remover_usuario(usuario_id)

        self.usuarios.append(PermisoUsuario(
            usuario_id=usuario_id,
            nivel=nivel,
            fecha_expiracion=fecha_expiracion
        ))

    def remover_usuario(self, usuario_id: int) -> bool:
        """Remueve los permisos de un usuario."""
        for i, u in enumerate(self.usuarios):
            if u.usuario_id == usuario_id:
                self.usuarios.pop(i)
                return True
        return False

    def obtener_permiso_usuario(self, usuario_id: int) -> Optional[PermisoUsuario]:
        """Obtiene el permiso de un usuario específico."""
        for u in self.usuarios:
            if u.usuario_id == usuario_id:
                return u
        return None

    def verificar_acceso(self, usuario_id: int, propietario_id: int) -> Optional[NivelAcceso]:
        """
        Verifica el nivel de acceso de un usuario.

        Args:
            usuario_id: ID del usuario a verificar
            propietario_id: ID del propietario del documento

        Returns:
            Nivel de acceso o None si no tiene acceso
        """
        # El propietario siempre tiene acceso total
        if usuario_id == propietario_id:
            return NivelAcceso.PROPIETARIO

        # Verificar permiso individual
        permiso = self.obtener_permiso_usuario(usuario_id)
        if permiso and permiso.esta_vigente:
            return permiso.nivel

        # Verificar acceso público
        if self.publico:
            if self.fecha_expiracion_publica and datetime.now() >= self.fecha_expiracion_publica:
                return None
            return NivelAcceso.LECTOR

        return None

    def generar_enlace_compartido(self) -> str:
        """Genera un enlace único para compartir."""
        import uuid
        self.enlace_compartido = uuid.uuid4().hex[:16]
        return self.enlace_compartido

    def revocar_enlace_compartido(self) -> None:
        """Revoca el enlace compartido."""
        self.enlace_compartido = None

    def establecer_contrasena(self, contrasena: str) -> None:
        """Establece contraseña de protección."""
        import hashlib
        self.requiere_contrasena = True
        self.contrasena_hash = hashlib.sha256(contrasena.encode()).hexdigest()

    def verificar_contrasena(self, contrasena: str) -> bool:
        """Verifica la contraseña."""
        if not self.requiere_contrasena:
            return True

        import hashlib
        return self.contrasena_hash == hashlib.sha256(contrasena.encode()).hexdigest()

    def remover_contrasena(self) -> None:
        """Remueve la contraseña de protección."""
        self.requiere_contrasena = False
        self.contrasena_hash = None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'publico': self.publico,
            'requiere_contrasena': self.requiere_contrasena,
            'permite_descarga': self.permite_descarga,
            'permite_impresion': self.permite_impresion,
            'permite_copia': self.permite_copia,
            'fecha_expiracion_publica': (
                self.fecha_expiracion_publica.isoformat()
                if self.fecha_expiracion_publica else None
            ),
            'usuarios': [u.to_dict() for u in self.usuarios],
            'tiene_enlace_compartido': self.enlace_compartido is not None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PermisoDocumento':
        """Crea desde diccionario."""
        permisos = cls(
            publico=data.get('publico', False),
            requiere_contrasena=data.get('requiere_contrasena', False),
            permite_descarga=data.get('permite_descarga', True),
            permite_impresion=data.get('permite_impresion', True),
            permite_copia=data.get('permite_copia', True)
        )

        if data.get('fecha_expiracion_publica'):
            permisos.fecha_expiracion_publica = datetime.fromisoformat(
                data['fecha_expiracion_publica']
            )

        return permisos
