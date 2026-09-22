"""Cuerpos de la API de dispositivos (lo que envía el teléfono). Todo acotado en tamaño."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Enrolamiento(BaseModel):
    codigo: str = Field(..., min_length=8, max_length=64)
    id_instalacion: str = Field(
        ..., min_length=8, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$"
    )
    modo: Literal["propietario", "limitado"] = "limitado"
    fabricante: Optional[str] = Field(None, max_length=80)
    modelo: Optional[str] = Field(None, max_length=120)
    serie: Optional[str] = Field(None, max_length=80)
    imei: Optional[str] = Field(None, pattern=r"^\d{14,17}$")
    imeis: Optional[list[str]] = Field(None, max_length=4)   # todos los IMEI (doble SIM, eSIM), si la app puede leerlos
    android: Optional[str] = Field(None, max_length=40)
    version_app: Optional[str] = Field(None, max_length=40)


class Ubicacion(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    precision: Optional[float] = Field(None, ge=0, le=100000)
    hora: Optional[str] = Field(None, max_length=40)
    fuente: Optional[Literal["gps", "red", "fusion"]] = None


class Latido(BaseModel):
    bateria: Optional[int] = Field(None, ge=0, le=100)
    cargando: Optional[bool] = None
    almacenamiento_libre: Optional[int] = Field(None, ge=0)
    almacenamiento_total: Optional[int] = Field(None, ge=0)
    red: Optional[str] = Field(None, max_length=40)
    version_app: Optional[str] = Field(None, max_length=40)
    android: Optional[str] = Field(None, max_length=40)
    play_protect: Optional[bool] = None
    # Si la app sigue siendo administradora del dispositivo (modo limitado). Opcional: la 1.2.8 aún no lo manda.
    admin_activo: Optional[bool] = None
    # Wifi al que está conectado (nombre y MAC del punto de acceso); requiere el permiso de ubicación en Android.
    wifi_ssid: Optional[str] = Field(None, max_length=64)
    wifi_bssid: Optional[str] = Field(None, pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    imeis: Optional[list[str]] = Field(None, max_length=4)   # cuando la app puede leerlos (control completo)
    ubicacion: Optional[Ubicacion] = None


class WifiVista(BaseModel):
    bssid: str = Field(..., pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    rssi: Optional[int] = Field(None, ge=-127, le=20)
    ssid: Optional[str] = Field(None, max_length=64)


class ResultadoComando(BaseModel):
    estado: Literal["hecho", "fallido"]
    detalle: Optional[str] = Field(None, max_length=2000)
    wifis_vistas: Optional[list[WifiVista]] = Field(None, max_length=20)   # etapa 2: triangulación por puntos de acceso


class Acuse(BaseModel):
    leido_en: Optional[str] = Field(None, max_length=40)


TIPOS_EVENTO = (
    "arranque",
    "admin_desactivado",  # alguien quitó a la app como administradora del dispositivo
    "desinstalacion_intento",
    "permiso_revocado",
    "sim_cambiada",
    "imei_ajeno",  # el teléfono mandó un IMEI que ya pertenece a otro equipo registrado
    "otro",
)


class Evento(BaseModel):
    tipo: str = Field(..., max_length=40)
    detalle: Optional[dict] = None
