"""Seguridad → Tableros: flujo de correo, inicios de sesión, cumplimiento, configuración y Wazuh.

Solo operadores (superadmin y admin): los tableros muestran cuentas e IP de las personas. Cambiar la
configuración, solo superadmin, y queda en la auditoría. Las alertas y los informes están en
router_alertas.py y router_informes.py.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import require_operador, require_superadmin
from app.dns.ayudante import auditar, ayudante

from . import ajustes, consultas, zona

router = APIRouter(prefix="/api/seguridad", tags=["seguridad"])
SERVICIOS = ("webmail", "imap", "pop3", "smtp", "activesync", "panel")


def _db(r: Request):
    return r.app.state.db


async def periodo(r: Request, desde: str | None, hasta: str | None) -> tuple:
    """(inicio, fin, nombre de la zona) o 400 con el motivo."""
    cfg = await ajustes.leer(_db(r))
    nombre = zona.nombre(cfg["zona_horaria"])
    try:
        inicio, fin = consultas.rango(desde, hasta, zona.zona(cfg["zona_horaria"]))
    except consultas.RangoInvalido as e:
        raise HTTPException(400, str(e))
    return inicio, fin, nombre


@router.get("/resumen")
async def resumen(r: Request, admin: dict = Depends(require_operador)):
    try:
        return await consultas.resumen(_db(r))
    except Exception:
        raise HTTPException(503, "Faltan las tablas de los tableros: aplique migrations/2026-10-21-tableros-seguridad.sql")


@router.get("/flujo")
async def flujo(r: Request, desde: str | None = None, hasta: str | None = None,
                agrupar: Literal["hora", "dia"] | None = None, admin: dict = Depends(require_operador)):
    inicio, fin, nombre = await periodo(r, desde, hasta)
    return await consultas.flujo(_db(r), inicio, fin, consultas.agrupacion(inicio, fin, agrupar), nombre)


@router.get("/accesos")
async def accesos(r: Request, desde: str | None = None, hasta: str | None = None,
                  agrupar: Literal["hora", "dia"] | None = None, servicio: str | None = None,
                  admin: dict = Depends(require_operador)):
    if servicio and servicio not in SERVICIOS:
        raise HTTPException(400, "Servicio no válido")
    inicio, fin, nombre = await periodo(r, desde, hasta)
    db = _db(r)
    datos = await consultas.accesos(db, inicio, fin, consultas.agrupacion(inicio, fin, agrupar), nombre, servicio)
    datos["top_ips"] = await consultas.top_ips(db, inicio, fin)
    datos["top_cuentas"] = await consultas.top_cuentas(db, inicio, fin)
    return datos


@router.get("/cumplimiento")
async def cumplimiento(r: Request, desde: str | None = None, hasta: str | None = None,
                       admin: dict = Depends(require_operador)):
    inicio, fin, nombre = await periodo(r, desde, hasta)
    return await consultas.cumplimiento(_db(r), inicio, fin, nombre)


@router.get("/config")
async def ver_config(r: Request, admin: dict = Depends(require_operador)):
    cfg = await ajustes.leer(_db(r))
    return {**cfg, "zona_efectiva": zona.nombre(cfg["zona_horaria"])}


class Config(BaseModel):
    retencion_dias: int | None = None
    retencion_detalle_dias: int | None = None
    zona_horaria: str | None = None
    regla_pais_nuevo: bool | None = None
    regla_fallos_y_exito: bool | None = None
    regla_hora_inusual: bool | None = None
    regla_muchas_cuentas_ip: bool | None = None
    umbral_fallos: int | None = None
    ventana_fallos_min: int | None = None
    umbral_cuentas_ip: int | None = None
    hora_min_historial: int | None = None
    hora_porcentaje_max: int | None = None
    avisos: bool | None = None
    aviso_severidad_minima: str | None = None
    avisos_por_hora: int | None = None
    escalar_tras_horas: int | None = None


@router.put("/config")
async def guardar_config(body: Config, r: Request, admin: dict = Depends(require_superadmin)):
    db = _db(r)
    actual = await ajustes.leer(db)
    pedido = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        nuevo = ajustes.validar({**actual, **pedido})
    except ValueError as e:
        raise HTTPException(400, str(e))
    await ajustes.guardar(db, nuevo, admin["username"])
    cambios = {k: v for k, v in nuevo.items() if actual.get(k) != v}
    await auditar(r, admin, "seguridad_config", "tableros", cambios)
    return {"ok": True, **nuevo}


@router.get("/wazuh")
async def estado_wazuh(admin: dict = Depends(require_operador)):
    """Agente Wazuh de este servidor (opcional): instalado, conectado al manager o no."""
    try:
        return await ayudante("wazuh", "estado", tiempo=20)
    except HTTPException as e:
        if e.status_code == 503:
            return {"instalado": False}
        raise
