# -*- coding: utf-8 -*-
"""
Entidades de Formulario - Gestión de formularios PDF.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List

from ..value_objects.tipos_pdf import TipoCampoFormulario


@dataclass
class CampoFormulario:
    """
    Representa un campo individual de un formulario PDF.

    Attributes:
        nombre: Nombre único del campo
        tipo: Tipo de campo (texto, checkbox, radio, etc.)
        pagina: Página donde se ubica el campo
        coordenadas: Posición y dimensiones
        propiedades: Configuración del campo (obligatorio, formato, etc.)
        valor_defecto: Valor por defecto
    """

    nombre: str
    tipo: TipoCampoFormulario
    pagina: int
    coordenadas: Dict[str, float]
    propiedades: Dict[str, Any] = field(default_factory=dict)
    valor_defecto: Optional[Any] = None
    id: Optional[str] = None

    def __post_init__(self):
        """Inicialización de ID si no existe."""
        if not self.id:
            import uuid
            self.id = str(uuid.uuid4())[:8]

        # Propiedades por defecto según tipo
        if 'obligatorio' not in self.propiedades:
            self.propiedades['obligatorio'] = False

    @property
    def es_obligatorio(self) -> bool:
        """Indica si el campo es obligatorio."""
        return self.propiedades.get('obligatorio', False)

    def validar_valor(self, valor: Any) -> tuple[bool, Optional[str]]:
        """
        Valida un valor para este campo.

        Args:
            valor: Valor a validar

        Returns:
            Tupla (es_valido, mensaje_error)
        """
        # Validar obligatoriedad
        if self.es_obligatorio and not valor:
            return False, f"El campo '{self.nombre}' es obligatorio"

        # Validaciones específicas por tipo
        if self.tipo == TipoCampoFormulario.NUMERO and valor:
            try:
                float(valor)
            except (ValueError, TypeError):
                return False, f"El campo '{self.nombre}' debe ser numérico"

        if self.tipo == TipoCampoFormulario.EMAIL and valor:
            import re
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', str(valor)):
                return False, f"El campo '{self.nombre}' debe ser un email válido"

        if self.tipo == TipoCampoFormulario.FECHA and valor:
            try:
                from datetime import datetime
                datetime.strptime(str(valor), self.propiedades.get('formato_fecha', '%Y-%m-%d'))
            except ValueError:
                return False, f"El campo '{self.nombre}' tiene un formato de fecha inválido"

        # Validar longitud máxima
        max_length = self.propiedades.get('max_length')
        if max_length and valor and len(str(valor)) > max_length:
            return False, f"El campo '{self.nombre}' excede la longitud máxima de {max_length}"

        return True, None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'tipo': self.tipo.value if isinstance(self.tipo, TipoCampoFormulario) else self.tipo,
            'pagina': self.pagina,
            'coordenadas': self.coordenadas,
            'propiedades': self.propiedades,
            'valor_defecto': self.valor_defecto
        }


@dataclass
class Formulario:
    """
    Representa un formulario PDF completo.

    Attributes:
        documento_id: ID del documento que contiene el formulario
        nombre: Nombre del formulario
        campos: Lista de campos del formulario
        validaciones: Reglas de validación globales
        logica_condicional: Reglas de visibilidad/cálculo
    """

    documento_id: int
    campos: List[CampoFormulario] = field(default_factory=list)
    nombre: Optional[str] = None
    validaciones: Dict[str, Any] = field(default_factory=dict)
    logica_condicional: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def agregar_campo(self, campo: CampoFormulario) -> None:
        """Agrega un campo al formulario."""
        # Verificar que no exista un campo con el mismo nombre
        if any(c.nombre == campo.nombre for c in self.campos):
            raise ValueError(f"Ya existe un campo con el nombre '{campo.nombre}'")
        self.campos.append(campo)
        self.updated_at = datetime.now()

    def eliminar_campo(self, nombre_campo: str) -> bool:
        """Elimina un campo por su nombre."""
        for i, campo in enumerate(self.campos):
            if campo.nombre == nombre_campo:
                self.campos.pop(i)
                self.updated_at = datetime.now()
                return True
        return False

    def obtener_campo(self, nombre: str) -> Optional[CampoFormulario]:
        """Obtiene un campo por su nombre."""
        for campo in self.campos:
            if campo.nombre == nombre:
                return campo
        return None

    def obtener_campos_pagina(self, pagina: int) -> List[CampoFormulario]:
        """Obtiene todos los campos de una página."""
        return [c for c in self.campos if c.pagina == pagina]

    def validar_respuestas(self, respuestas: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Valida un conjunto de respuestas.

        Args:
            respuestas: Diccionario con valores por nombre de campo

        Returns:
            Tupla (todo_valido, lista_errores)
        """
        errores = []

        for campo in self.campos:
            valor = respuestas.get(campo.nombre)
            valido, error = campo.validar_valor(valor)
            if not valido:
                errores.append(error)

        return len(errores) == 0, errores

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'id': self.id,
            'documento_id': self.documento_id,
            'nombre': self.nombre,
            'campos': [c.to_dict() for c in self.campos],
            'validaciones': self.validaciones,
            'logica_condicional': self.logica_condicional,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


@dataclass
class RespuestaFormulario:
    """
    Representa las respuestas a un formulario.
    """

    formulario_id: int
    usuario_id: int
    datos: Dict[str, Any] = field(default_factory=dict)
    completado: bool = False
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    def establecer_valor(self, nombre_campo: str, valor: Any) -> None:
        """Establece el valor de un campo."""
        self.datos[nombre_campo] = valor

    def obtener_valor(self, nombre_campo: str) -> Optional[Any]:
        """Obtiene el valor de un campo."""
        return self.datos.get(nombre_campo)

    def marcar_completado(self) -> None:
        """Marca el formulario como completado."""
        self.completado = True

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'id': self.id,
            'formulario_id': self.formulario_id,
            'usuario_id': self.usuario_id,
            'datos': self.datos,
            'completado': self.completado,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
