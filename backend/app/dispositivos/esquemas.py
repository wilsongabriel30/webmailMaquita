"""Cuerpos de la API de dispositivos (lo que envía el teléfono). Todo acotado en tamaño."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Enrolamiento(BaseModel):
    codigo: str = Field(..., min_length=8, max_length=64)
    id_instalacion: str = Field(..., min_length=8, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$")
    modo: Literal["propietario", "limitado"] = "limitado"
    fabricante: Optional[str] = Field(None, max_length=80)
    modelo: Optional[str] = Field(None, max_length=120)
    serie: Optional[str] = Field(None, max_length=80)
    imei: Optional[str] = Field(None, pattern=r"^\d{14,17}$")
    android: Optional[str] = Field(None, max_length=40)
    version_app: Optional[str] = Field(None, max_length=40)


class Ubicacion(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    precision: Optional[float] = Field(None, ge=0, le=100000)
    hora: Optional[str] = Field(None, max_length=40)


class Latido(BaseModel):
    bateria: Optional[int] = Field(None, ge=0, le=100)
    cargando: Optional[bool] = None
    almacenamiento_libre: Optional[int] = Field(None, ge=0)
    almacenamiento_total: Optional[int] = Field(None, ge=0)
    red: Optional[str] = Field(None, max_length=40)
    version_app: Optional[str] = Field(None, max_length=40)
    android: Optional[str] = Field(None, max_length=40)
    play_protect: Optional[bool] = None
    ubicacion: Optional[Ubicacion] = None


class ResultadoComando(BaseModel):
    estado: Literal["hecho", "fallido"]
    detalle: Optional[str] = Field(None, max_length=2000)


class Acuse(BaseModel):
    leido_en: Optional[str] = Field(None, max_length=40)


TIPOS_EVENTO = (
    "arranque",
    "admin_desactivado",       # alguien quitó a la app como administradora del dispositivo
    "desinstalacion_intento",
    "permiso_revocado",
    "sim_cambiada",
    "otro",
)


class Evento(BaseModel):
    tipo: str = Field(..., max_length=40)
    detalle: Optional[dict] = None
