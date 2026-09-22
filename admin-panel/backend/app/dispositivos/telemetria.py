"""Panel · Dispositivos: portal de telemetría (AE-03, 22/09/2026).

Telemetría DEL EQUIPO, no de la persona: batería, almacenamiento, red, versiones, administración,
Play Protect, eventos de seguridad, acuses y alertas. Sin contenido, sin apps de uso, sin navegación y
sin ubicación (esa sigue solo bajo la regla de la fase 2). Todo GET: lo puede ver el rol `viewer`
(dirección); la exportación CSV queda en `admin_audit`.
"""

import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from app.auth.dependencies import get_current_admin
from app.dispositivos import version_publicada
from app.dispositivos.comun import auditar, db

router = APIRouter(prefix="/api/dispositivos/telemetria", tags=["dispositivos"])

_GRAVES = "('admin_desactivado', 'desinstalacion_intento', 'sim_cambiada')"
_FLOTA = f"""
SELECT e.id, e.nombre, e.fabricante, e.modelo, e.custodio_email, e.custodio_nombre, e.sede, e.centro_costo, e.estado, e.modo,
       e.ultimo_contacto, e.bateria, e.cargando, e.almacenamiento_libre, e.almacenamiento_total, e.red, e.version_app, e.android,
       e.play_protect, e.admin_activo, e.enrolado_en, e.ancla_sede, e.ancla_en, e.wifi_ssid,
       (SELECT count(*) FROM disp_eventos ev WHERE ev.equipo_id = e.id AND ev.recibido_en > NOW() - interval '7 days' AND ev.tipo IN {_GRAVES}) AS eventos_rojos_7d,
       (SELECT count(*) FROM disp_eventos ev WHERE ev.equipo_id = e.id AND ev.visto_en IS NULL AND ev.tipo IN {_GRAVES}) AS eventos_sin_revisar,
       (SELECT count(*) FROM disp_mensajes_equipos me JOIN disp_mensajes m ON m.id = me.mensaje_id
         WHERE me.equipo_id = e.id AND m.nivel = 'urgente' AND m.requiere_acuse AND me.leido_en IS NULL
           AND (m.caduca_en IS NULL OR m.caduca_en > NOW())) AS urgentes_sin_acuse,
       (SELECT count(*) FROM disp_alertas a WHERE a.equipo_id = e.id AND a.hasta IS NULL) AS alertas_abiertas,
       (SELECT json_agg(json_build_object('tipo', a.tipo, 'desde', a.desde) ORDER BY a.desde) FROM disp_alertas a WHERE a.equipo_id = e.id AND a.hasta IS NULL) AS alertas
  FROM disp_equipos e WHERE e.estado <> 'baja'
 ORDER BY e.estado, e.nombre, e.id"""


def _semaforo(ultimo) -> str:
    if not ultimo:
        return "rojo"
    horas = (datetime.now(timezone.utc) - ultimo).total_seconds() / 3600
    return "verde" if horas < 1 else "amarillo" if horas < 24 else "rojo"


def _fila(f, pub: dict) -> dict:
    d = dict(f)
    d["semaforo"] = _semaforo(d["ultimo_contacto"])
    tot, lib = d.get("almacenamiento_total") or 0, d.get("almacenamiento_libre")
    d["almacenamiento_pct"] = round(lib * 100 / tot, 1) if tot and lib is not None else None
    d["version_atrasada"] = version_publicada.atrasada(d.get("version_app"), pub)
    if d.get("admin_activo") is None:
        # La app no lo reporta aún: en control completo siempre es administradora; en limitado se
        # deduce del último evento de seguridad sin revisar.
        d["admin_activo"] = True if d["modo"] == "propietario" else (None if d["eventos_sin_revisar"] == 0 else False)
    if isinstance(d.get("alertas"), str):
        d["alertas"] = json.loads(d["alertas"])
    return d


@router.get("/flota")
async def flota(request: Request, admin: dict = Depends(get_current_admin)):
    pub = version_publicada.leer()
    filas = [_fila(f, pub) for f in await db(request).fetch(_FLOTA)]
    activos = [f for f in filas if f["estado"] in ("activo", "perdido")]
    return {
        "publicada": pub,
        "totales": {
            "equipos": len(activos),
            "reportando_hoy": sum(1 for f in activos if f["semaforo"] != "rojo"),
            "rojo": sum(1 for f in activos if f["semaforo"] == "rojo"),
            "con_alertas": sum(1 for f in activos if f["alertas_abiertas"]),
        },
        "equipos": filas,
    }


@router.get("/flota.csv")
async def flota_csv(request: Request, admin: dict = Depends(get_current_admin)):
    pub = version_publicada.leer()
    filas = [_fila(f, pub) for f in await db(request).fetch(_FLOTA)]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Equipo", "Custodio", "Correo custodio", "Sede", "Centro de costo", "Fabricante", "Modelo", "Estado", "Modo", "Semáforo",
                "Último contacto", "Batería %", "Cargando", "Almacenamiento libre %", "Almacenamiento libre GB", "Almacenamiento total GB", "Red",
                "Versión app", "Versión publicada", "Atrasada", "Android", "Admin. activa", "Play Protect", "Eventos rojos 7 d",
                "Urgentes sin acuse", "Alertas abiertas"])
    gb = lambda b: round(b / 1073741824, 1) if b else ""  # noqa: E731
    for f in filas:
        w.writerow([f["nombre"], f["custodio_nombre"] or "", f["custodio_email"] or "", f["sede"] or "", f["centro_costo"] or "",
                    f["fabricante"] or "", f["modelo"] or "", f["estado"], f["modo"], f["semaforo"],
                    f["ultimo_contacto"].astimezone().strftime("%Y-%m-%d %H:%M") if f["ultimo_contacto"] else "",
                    f["bateria"] if f["bateria"] is not None else "", "sí" if f["cargando"] else "no" if f["cargando"] is not None else "",
                    f["almacenamiento_pct"] if f["almacenamiento_pct"] is not None else "", gb(f["almacenamiento_libre"]), gb(f["almacenamiento_total"]),
                    f["red"] or "", f["version_app"] or "", pub.get("versionName", ""), "sí" if f["version_atrasada"] else "no", f["android"] or "",
                    "" if f["admin_activo"] is None else "sí" if f["admin_activo"] else "no",
                    "" if f["play_protect"] is None else "sí" if f["play_protect"] else "no",
                    f["eventos_rojos_7d"], f["urgentes_sin_acuse"], f["alertas_abiertas"]])
    await auditar(request, admin, "dispositivo_telemetria_csv", "flota", {"equipos": len(filas)})
    nombre = f"telemetria-telefonos-{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


def _j(v):
    return json.loads(v) if isinstance(v, str) else v


@router.get("/equipos/{equipo_id}")
async def ficha(equipo_id: int, request: Request, rango: str = Query("24h"), admin: dict = Depends(get_current_admin)):
    """Series para las gráficas (24h y 7d desde los latidos; 30d desde el resumen diario), línea de
    tiempo de eventos, mensajes con acuse, comandos y versiones por las que pasó."""
    d = db(request)
    e = await d.fetchrow("SELECT id, nombre, fabricante, modelo, custodio_nombre, custodio_email, modo, estado, version_app, android, enrolado_en FROM disp_equipos WHERE id = $1", equipo_id)
    if e is None:
        raise HTTPException(404, "Equipo no encontrado")
    rango = rango if rango in ("24h", "7d", "30d") else "24h"
    if rango == "30d":
        serie = [dict(x) for x in await d.fetch(
            "SELECT dia, latidos, bateria_min, bateria_max, bateria_prom, alm_libre_min, alm_libre_prom, alm_total, version_app "
            "FROM disp_resumen_diario WHERE equipo_id = $1 AND dia > CURRENT_DATE - 31 ORDER BY dia", equipo_id)]
    else:
        serie = [{"t": x["recibido_en"], **{k: _j(x["datos"]).get(k) for k in ("bateria", "cargando", "almacenamiento_libre", "almacenamiento_total", "red")}}
                 for x in await d.fetch(
                     "SELECT recibido_en, datos FROM disp_latidos WHERE equipo_id = $1 AND recibido_en > NOW() - make_interval(hours => $2) ORDER BY recibido_en",
                     equipo_id, 24 if rango == "24h" else 24 * 7)]
    eventos = await d.fetch("SELECT id, tipo, detalle, recibido_en, visto_por, visto_en FROM disp_eventos WHERE equipo_id = $1 ORDER BY recibido_en DESC LIMIT 100", equipo_id)
    mensajes = await d.fetch(
        """SELECT m.id, m.titulo, m.nivel, m.requiere_acuse, m.creado_por, m.creado_en, me.entregado_en, me.leido_en, e.custodio_nombre, e.custodio_email
             FROM disp_mensajes_equipos me JOIN disp_mensajes m ON m.id = me.mensaje_id JOIN disp_equipos e ON e.id = me.equipo_id
            WHERE me.equipo_id = $1 ORDER BY m.creado_en DESC LIMIT 50""", equipo_id)
    comandos = await d.fetch("SELECT id, tipo, estado, creado_por, creado_en, entregado_en, terminado_en, resultado, motivo FROM disp_comandos WHERE equipo_id = $1 ORDER BY creado_en DESC LIMIT 50", equipo_id)
    versiones = await d.fetch(
        """SELECT version_app, min(dia) AS desde, max(dia) AS hasta FROM disp_resumen_diario WHERE equipo_id = $1 AND version_app IS NOT NULL GROUP BY version_app
           UNION ALL
           SELECT datos->>'version_app', min(recibido_en)::date, max(recibido_en)::date FROM disp_latidos WHERE equipo_id = $1 AND datos ? 'version_app' GROUP BY 1
           ORDER BY desde""", equipo_id)
    vistas: dict[str, dict] = {}
    for v in versiones:
        cur = vistas.setdefault(v["version_app"], {"version": v["version_app"], "desde": v["desde"], "hasta": v["hasta"]})
        cur["desde"], cur["hasta"] = min(cur["desde"], v["desde"]), max(cur["hasta"], v["hasta"])
    alertas = await d.fetch("SELECT id, tipo, detalle, desde, hasta, avisada_en FROM disp_alertas WHERE equipo_id = $1 ORDER BY desde DESC LIMIT 50", equipo_id)
    return {
        "equipo": dict(e), "rango": rango, "serie": serie, "publicada": version_publicada.leer(),
        "eventos": [{**dict(x), "detalle": _j(x["detalle"])} for x in eventos],
        "mensajes": [dict(x) for x in mensajes],
        "comandos": [{**dict(x), "resultado": _j(x["resultado"])} for x in comandos],
        "versiones": sorted(vistas.values(), key=lambda v: v["desde"]),
        "alertas": [{**dict(x), "detalle": _j(x["detalle"])} for x in alertas],
    }
