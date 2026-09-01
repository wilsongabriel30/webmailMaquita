"""Esquemas Pydantic de T-34 (todo en español; los campos heredados de task_cards conservan su nombre)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

ESTADOS = ('espera', 'pendiente', 'en_curso', 'completada', 'vencida')
PRIORIDADES = ('low', 'medium', 'high', 'urgent')
RECURRENCIAS = ('daily', 'weekdays', 'weekly', 'monthly', 'yearly')


class CorreoRef(BaseModel):
    folder: str
    uid: int
    subject: str = ''
    from_: str = Field('', alias='from')
    model_config = {'populate_by_name': True}


class TareaAsignar(BaseModel):
    titulo: str
    descripcion: str = ''
    asignados: list[str] = Field(default_factory=list)   # correos
    plazo: Optional[datetime] = None
    prioridad: str = 'medium'
    etiquetas: list[str] = Field(default_factory=list)
    recurrencia: Optional[str] = None
    activa_tarea_id: Optional[uuid.UUID] = None          # cadena: tarea que, al completarse, ACTIVA a esta
    en_espera: bool = False                              # nace en 'espera' hasta que se complete aquella
    escalar_a: Optional[str] = None                      # jefe que recibe el escalamiento (si no, por departamento)
    correo: Optional[CorreoRef] = None
    subtareas: list[str] = Field(default_factory=list)


class TareaEditar(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    asignados: Optional[list[str]] = None
    plazo: Optional[datetime] = None
    quitar_plazo: bool = False
    prioridad: Optional[str] = None
    etiquetas: Optional[list[str]] = None
    recurrencia: Optional[str] = None
    quitar_recurrencia: bool = False
    activa_tarea_id: Optional[uuid.UUID] = None
    escalar_a: Optional[str] = None


class CambioEstado(BaseModel):
    estado: str


class Rechazo(BaseModel):
    motivo: str = ''


class ComentarioNuevo(BaseModel):
    texto: str


class ComentarioOut(BaseModel):
    id: uuid.UUID
    autor: str
    texto: str
    menciones: list[str]
    creado_en: datetime


class EscalamientoConfig(BaseModel):
    departamento: str
    jefe_email: str
    dias: int = 2


class TareaOut(BaseModel):
    id: uuid.UUID
    titulo: str
    descripcion: str
    asignados: list[str]
    asignado_por: str
    plazo: Optional[datetime]
    prioridad: str
    etiquetas: list[str]
    estado: str
    semaforo: str                       # verde | amarillo | rojo | gris
    aceptacion: str
    motivo_rechazo: str
    recurrencia: Optional[str]
    activa_tarea_id: Optional[uuid.UUID]   # tarea que ESTA activa al completarse (siguiente de la cadena)
    activada_por: Optional[uuid.UUID]     # tarea que la activa (si está en espera)
    escalar_a: Optional[str]
    escalado_en: Optional[datetime]
    correo: Optional[dict[str, Any]]
    subtareas_total: int = 0
    subtareas_hechas: int = 0
    comentarios: int = 0
    completada_por: Optional[str]
    completada_en: Optional[datetime]
    creada_en: datetime
    actualizada_en: datetime
    url: str
