"""Informes descargables de los tableros (CSV y HTML imprimible → PDF desde el navegador).

Cada descarga queda en la auditoría del panel (quién, qué informe y qué periodo): son datos personales
(cuentas e IP) que salen del panel.
"""

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from app.auth.dependencies import require_operador
from app.dns.ayudante import auditar

from . import consultas, informes
from .router import periodo

router = APIRouter(prefix="/api/seguridad/informes", tags=["seguridad"])
_CABECERAS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def _db(r: Request):
    return r.app.state.db


async def _filas(db, tipo: str, inicio, fin, nombre: str) -> list:
    if tipo == "flujo":
        return (await consultas.flujo(db, inicio, fin, consultas.agrupacion(inicio, fin, None), nombre))["serie"]
    if tipo == "accesos":
        return (await consultas.accesos(db, inicio, fin, consultas.agrupacion(inicio, fin, None), nombre, None))["serie"]
    if tipo == "ips":
        return await consultas.top_ips(db, inicio, fin, 1000)
    if tipo == "cuentas":
        return await consultas.top_cuentas(db, inicio, fin, 1000)
    if tipo == "alertas":
        filas = await db.fetch("SELECT * FROM seg_alertas WHERE creada >= $1 AND creada < $2 ORDER BY creada", inicio, fin)
        return [consultas.alerta_dict(f) for f in filas]
    datos = await consultas.cumplimiento(db, inicio, fin, nombre)
    return datos["recientes"] or []


def _texto_periodo(inicio: datetime, fin: datetime) -> str:
    return f"{inicio:%Y-%m-%d} a {(fin - timedelta(days=1)):%Y-%m-%d}"


@router.get("/{tipo}.csv")
async def csv(tipo: Literal["flujo", "accesos", "ips", "cuentas", "alertas", "cumplimiento"], r: Request,
              desde: str | None = None, hasta: str | None = None, admin: dict = Depends(require_operador)):
    inicio, fin, nombre = await periodo(r, desde, hasta)
    filas = await _filas(_db(r), tipo, inicio, fin, nombre)
    await auditar(r, admin, "seguridad_informe", f"{tipo}.csv", {"periodo": _texto_periodo(inicio, fin), "filas": len(filas)})
    archivo = f"seguridad-{tipo}-{inicio:%Y%m%d}-{(fin - timedelta(days=1)):%Y%m%d}.csv"
    return Response(informes.a_csv(tipo, filas), media_type="text/csv; charset=utf-8",
                    headers={**_CABECERAS, "Content-Disposition": f'attachment; filename="{archivo}"'})


@router.get("/resumen.html", response_class=HTMLResponse)
async def resumen_html(r: Request, desde: str | None = None, hasta: str | None = None,
                       admin: dict = Depends(require_operador)):
    inicio, fin, nombre = await periodo(r, desde, hasta)
    db = _db(r)
    flujo = await consultas.flujo(db, inicio, fin, "day", nombre)
    accesos = await consultas.accesos(db, inicio, fin, "day", nombre, None)
    alertas = [consultas.alerta_dict(f) for f in await db.fetch(
        "SELECT * FROM seg_alertas WHERE creada >= $1 AND creada < $2 ORDER BY creada DESC LIMIT 500", inicio, fin)]
    cumpl = await consultas.cumplimiento(db, inicio, fin, nombre)
    t = flujo["totales"]
    ok = sum(x["ok"] for x in accesos["por_servicio"])
    fallos = sum(x["fallos"] for x in accesos["por_servicio"])
    kpis = {
        "Entregados a buzones": t.get("recibidos", 0), "Enviados fuera": t.get("enviados", 0),
        "Rechazados": t.get("rechazados", 0) + t.get("rechazados_filtro", 0),
        "Spam": t.get("spam_rechazado", 0) + t.get("spam_marcado", 0),
        "Accesos correctos": ok, "Accesos fallidos": fallos, "Alertas": len(alertas),
        "Exportaciones eDiscovery": len(cumpl["exportaciones"] or []),
    }
    secciones = [
        ("Flujo de correo por día", "flujo", flujo["serie"]),
        ("Inicios de sesión por día y servicio", "accesos", accesos["serie"]),
        ("IP con más fallos", "ips", await consultas.top_ips(db, inicio, fin, 50)),
        ("Cuentas con más fallos", "cuentas", await consultas.top_cuentas(db, inicio, fin, 50)),
        ("Alertas de anomalías", "alertas", alertas),
        ("Actividad de cumplimiento (auditoría del panel)", "cumplimiento", cumpl["recientes"] or []),
    ]
    await auditar(r, admin, "seguridad_informe", "resumen.html", {"periodo": _texto_periodo(inicio, fin)})
    cuerpo = informes.a_html("Informe de seguridad del correo", _texto_periodo(inicio, fin),
                             datetime.now().strftime("%Y-%m-%d %H:%M"), kpis, secciones)
    return HTMLResponse(cuerpo, headers={**_CABECERAS, "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
