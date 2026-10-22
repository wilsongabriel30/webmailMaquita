"""Lecturas de los tableros. Todo sale de las tablas agregadas (seg_*) o de tablas pequeñas que ya
existían (casos de eDiscovery, retenciones, auditoría); ninguna consulta recorre registros."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from zoneinfo import ZoneInfo

MAX_DIAS = 400
_RE_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")


class RangoInvalido(ValueError):
    pass


def rango(desde: str | None, hasta: str | None, zona: ZoneInfo, hoy: date | None = None) -> tuple:
    """Fechas «AAAA-MM-DD» (en la zona de los tableros) → (inicio, fin exclusivo) con zona.

    Por omisión, los últimos 7 días contando hoy. Como mucho MAX_DIAS días."""
    hoy = hoy or datetime.now(zona).date()
    try:
        d = date.fromisoformat(desde) if desde and _RE_FECHA.fullmatch(desde) else None
        h = date.fromisoformat(hasta) if hasta and _RE_FECHA.fullmatch(hasta) else None
    except ValueError:
        raise RangoInvalido("Fecha no válida (AAAA-MM-DD)")
    if (desde and d is None) or (hasta and h is None):
        raise RangoInvalido("Fecha no válida (AAAA-MM-DD)")
    h = h or hoy
    d = d or (h - timedelta(days=6))
    if d > h:
        raise RangoInvalido("«desde» es posterior a «hasta»")
    if (h - d).days + 1 > MAX_DIAS:
        raise RangoInvalido(f"El rango no puede pasar de {MAX_DIAS} días")
    return datetime.combine(d, time.min, zona), datetime.combine(h + timedelta(days=1), time.min, zona)


def agrupacion(inicio: datetime, fin: datetime, pedida: str | None) -> str:
    """Por hora solo hasta 7 días (más serían demasiados puntos); si no, por día."""
    if pedida == "hora" and fin - inicio <= timedelta(days=7):
        return "hour"
    if pedida == "dia":
        return "day"
    return "hour" if fin - inicio <= timedelta(days=2) else "day"


def _cubo(paso: str) -> str:
    # $3 = zona horaria: los días empiezan a medianoche local, no UTC.
    return f"date_trunc('{paso}', hora AT TIME ZONE $3::text)"


async def flujo(db, inicio, fin, paso: str, zona_nombre: str) -> dict:
    filas = await db.fetch(
        f"SELECT {_cubo(paso)} AS t, sum(recibidos) AS recibidos, sum(enviados) AS enviados, sum(rebotados) AS rebotados, "
        "sum(diferidos) AS diferidos, sum(rechazados) AS rechazados, sum(rechazados_filtro) AS rechazados_filtro, "
        "sum(analizados) AS analizados, sum(spam_rechazado) AS spam_rechazado, sum(spam_marcado) AS spam_marcado, "
        "sum(spam_aplazado) AS spam_aplazado, max(en_cola) AS en_cola "
        "FROM seg_flujo_hora WHERE hora >= $1 AND hora < $2 GROUP BY 1 ORDER BY 1",
        inicio, fin, zona_nombre)
    serie = [{k: (v.isoformat() if isinstance(v, datetime) else int(v or 0)) for k, v in dict(f).items()} for f in filas]
    totales = {k: sum(p[k] for p in serie) for k in serie[0] if k not in ("t", "en_cola")} if serie else {}
    cola = await db.fetchval("SELECT en_cola FROM seg_flujo_hora WHERE en_cola IS NOT NULL ORDER BY hora DESC LIMIT 1")
    return {"paso": paso, "serie": serie, "totales": totales, "cola_actual": cola}


async def accesos(db, inicio, fin, paso: str, zona_nombre: str, servicio: str | None) -> dict:
    filtro = " AND servicio = $4" if servicio else ""
    extra = [servicio] if servicio else []
    serie = await db.fetch(
        f"SELECT {_cubo(paso)} AS t, servicio, sum(ok) AS ok, sum(fallos) AS fallos FROM seg_accesos_hora "
        f"WHERE hora >= $1 AND hora < $2{filtro} GROUP BY 1, 2 ORDER BY 1", inicio, fin, zona_nombre, *extra)
    por_servicio = await db.fetch(
        "SELECT servicio, sum(ok) AS ok, sum(fallos) AS fallos FROM seg_accesos_hora "
        f"WHERE hora >= $1 AND hora < $2{filtro.replace('$4', '$3')} GROUP BY 1 ORDER BY 2 DESC", inicio, fin, *extra)
    por_pais = await db.fetch(
        "SELECT pais, sum(ok) AS ok, sum(fallos) AS fallos FROM seg_accesos_hora "
        f"WHERE hora >= $1 AND hora < $2{filtro.replace('$4', '$3')} GROUP BY 1 ORDER BY sum(ok) + sum(fallos) DESC LIMIT 40",
        inicio, fin, *extra)
    return {
        "paso": paso,
        "serie": [{"t": f["t"].isoformat(), "servicio": f["servicio"], "ok": int(f["ok"]), "fallos": int(f["fallos"])} for f in serie],
        "por_servicio": [dict(servicio=f["servicio"], ok=int(f["ok"]), fallos=int(f["fallos"])) for f in por_servicio],
        "por_pais": [dict(pais=f["pais"], ok=int(f["ok"]), fallos=int(f["fallos"])) for f in por_pais],
    }


async def top_ips(db, inicio, fin, limite: int = 25) -> list:
    filas = await db.fetch(
        "SELECT ip, max(pais) AS pais, sum(fallos) AS fallos, sum(ok) AS ok, count(DISTINCT cuenta) AS cuentas, "
        "array_agg(DISTINCT servicio) AS servicios, max(hora) AS ultima FROM seg_accesos_detalle "
        "WHERE hora >= $1 AND hora < $2 AND ip <> '' GROUP BY ip HAVING sum(fallos) > 0 "
        "ORDER BY sum(fallos) DESC LIMIT $3", inicio, fin, limite)
    return [{"ip": f["ip"], "pais": f["pais"], "fallos": int(f["fallos"]), "ok": int(f["ok"]), "cuentas": int(f["cuentas"]),
             "servicios": sorted(f["servicios"] or []), "ultima": f["ultima"].isoformat()} for f in filas]


async def top_cuentas(db, inicio, fin, limite: int = 25) -> list:
    filas = await db.fetch(
        "SELECT cuenta, sum(fallos) AS fallos, sum(ok) AS ok, count(DISTINCT ip) FILTER (WHERE fallos > 0) AS ips, "
        "count(DISTINCT pais) FILTER (WHERE fallos > 0) AS paises, max(hora) AS ultima FROM seg_accesos_detalle "
        "WHERE hora >= $1 AND hora < $2 AND cuenta <> '' GROUP BY cuenta HAVING sum(fallos) > 0 "
        "ORDER BY sum(fallos) DESC LIMIT $3", inicio, fin, limite)
    return [{"cuenta": f["cuenta"], "fallos": int(f["fallos"]), "ok": int(f["ok"]), "ips": int(f["ips"]),
             "paises": int(f["paises"]), "ultima": f["ultima"].isoformat()} for f in filas]


# Acciones de la auditoría del panel que son del módulo de cumplimiento.
_ACCIONES_CUMPLIMIENTO = ("action LIKE 'ediscovery%' OR action LIKE 'custodian%' OR action LIKE '%hold%' "
                          "OR action LIKE 'retention%' OR action LIKE 'case%' OR action IN ('mail_read', 'mail_export')")


async def _seguro(consulta, *args, db):
    """Una fuente de cumplimiento que falta en esta instalación no tumba el tablero entero."""
    try:
        return await db.fetch(consulta, *args)
    except Exception:
        return None


async def cumplimiento(db, inicio, fin, zona_nombre: str) -> dict:
    por_dia = "date_trunc('day', {c} AT TIME ZONE $3::text)"
    busquedas = await _seguro(
        f"SELECT {por_dia.format(c='executed_at')} AS t, count(*) AS n, sum(result_count) AS resultados "
        "FROM ediscovery_searches WHERE executed_at >= $1 AND executed_at < $2 GROUP BY 1 ORDER BY 1",
        inicio, fin, zona_nombre, db=db)
    exportaciones = await _seguro(
        "SELECT id, case_id, exported_by, exported_at, total_messages, export_format, reason FROM ediscovery_exports "
        "WHERE exported_at >= $1 AND exported_at < $2 ORDER BY exported_at DESC LIMIT 200", inicio, fin, db=db)
    retenciones = await _seguro(
        "SELECT count(*) FILTER (WHERE is_active) AS activas, "
        "count(*) FILTER (WHERE enabled_at >= $1 AND enabled_at < $2) AS puestas, "
        "count(*) FILTER (WHERE released_at >= $1 AND released_at < $2) AS liberadas FROM legal_holds", inicio, fin, db=db)
    politicas = await _seguro(
        "SELECT name, is_active, max_age_days, action, last_run, messages_affected FROM retention_policies ORDER BY name",
        db=db)
    acciones = await _seguro(
        f"SELECT {por_dia.format(c='created_at')} AS t, action, count(*) AS n FROM admin_audit "
        f"WHERE created_at >= $1 AND created_at < $2 AND ({_ACCIONES_CUMPLIMIENTO}) GROUP BY 1, 2 ORDER BY 1",
        inicio, fin, zona_nombre, db=db)
    recientes = await _seguro(
        f"SELECT created_at, admin_username, action, target, ip_address FROM admin_audit "
        f"WHERE created_at >= $1 AND created_at < $2 AND ({_ACCIONES_CUMPLIMIENTO}) ORDER BY created_at DESC LIMIT 100",
        inicio, fin, db=db)
    webmail = await _seguro(
        "SELECT action, count(*) AS n FROM user_activity_log WHERE category = 'compliance' "
        "AND created_at >= $1 AND created_at < $2 GROUP BY 1 ORDER BY 2 DESC", inicio, fin, db=db)

    def _iso(v):
        return v.isoformat() if isinstance(v, (datetime, date)) else v

    def _filas(r):
        return None if r is None else [{k: _iso(v) for k, v in dict(f).items()} for f in r]

    ret = _filas(retenciones)
    return {
        "busquedas": _filas(busquedas), "exportaciones": _filas(exportaciones),
        "retenciones": ret[0] if ret else None, "politicas": _filas(politicas),
        "acciones": _filas(acciones), "recientes": _filas(recientes), "webmail": _filas(webmail),
    }


async def alertas(db, estado: str | None, severidad: str | None, limite: int = 200) -> dict:
    condiciones, args = [], []
    if estado == "pendientes":
        condiciones.append("estado <> 'cerrada'")
    elif estado:
        args.append(estado)
        condiciones.append(f"estado = ${len(args)}")
    if severidad:
        args.append(severidad)
        condiciones.append(f"severidad = ${len(args)}")
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    args.append(limite)
    filas = await db.fetch(f"SELECT * FROM seg_alertas {where} ORDER BY creada DESC LIMIT ${len(args)}", *args)
    cuenta = await db.fetch("SELECT estado, severidad, count(*) AS n FROM seg_alertas WHERE estado <> 'cerrada' GROUP BY 1, 2")
    return {"alertas": [alerta_dict(f) for f in filas],
            "abiertas": {f"{f['estado']}:{f['severidad']}": int(f["n"]) for f in cuenta}}


def alerta_dict(f) -> dict:
    d = dict(f)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    if isinstance(d.get("detalles"), str):
        import json

        try:
            d["detalles"] = json.loads(d["detalles"])
        except ValueError:
            pass
    return d


async def resumen(db) -> dict:
    """Cifras de las últimas 24 h para la cabecera de los tableros."""
    f = await db.fetchrow(
        "SELECT COALESCE(sum(recibidos), 0) AS recibidos, COALESCE(sum(enviados), 0) AS enviados, "
        "COALESCE(sum(rechazados) + sum(rechazados_filtro), 0) AS rechazados, "
        "COALESCE(sum(spam_rechazado) + sum(spam_marcado), 0) AS spam "
        "FROM seg_flujo_hora WHERE hora >= now() - interval '24 hours'")
    a = await db.fetchrow(
        "SELECT COALESCE(sum(ok), 0) AS ok, COALESCE(sum(fallos), 0) AS fallos FROM seg_accesos_hora "
        "WHERE hora >= now() - interval '24 hours'")
    cola = await db.fetchval("SELECT en_cola FROM seg_flujo_hora WHERE en_cola IS NOT NULL ORDER BY hora DESC LIMIT 1")
    abiertas = await db.fetchval("SELECT count(*) FROM seg_alertas WHERE estado = 'abierta'")
    altas = await db.fetchval("SELECT count(*) FROM seg_alertas WHERE estado = 'abierta' AND severidad = 'alta'")
    pasada = await db.fetchrow("SELECT valor, actualizado FROM seg_estado WHERE clave = 'ultima_pasada'")
    valor = pasada["valor"] if pasada else None
    if isinstance(valor, str):
        import json

        valor = json.loads(valor)
    return {"correo_24h": {k: int(v) for k, v in dict(f).items()}, "accesos_24h": {k: int(v) for k, v in dict(a).items()},
            "cola": cola, "alertas_abiertas": int(abiertas or 0), "alertas_altas": int(altas or 0),
            "recolector": {"ultima": pasada["actualizado"].isoformat() if pasada else None, "resumen": valor}}
