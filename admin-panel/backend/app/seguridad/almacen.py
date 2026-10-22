"""Escrituras del recolector en las tablas seg_* (migrations/2026-10-21-tableros-seguridad.sql)."""

from __future__ import annotations

import json
from datetime import datetime

from .agregador import COLUMNAS_FLUJO

COLUMNAS_RSPAMD = ("analizados", "spam_rechazado", "spam_marcado", "spam_aplazado")


async def estado(db, clave: str, defecto=None):
    v = await db.fetchval("SELECT valor FROM seg_estado WHERE clave = $1", clave)
    if v is None:
        return defecto
    return json.loads(v) if isinstance(v, str) else v


async def guardar_estado(db, clave: str, valor) -> None:
    await db.execute(
        "INSERT INTO seg_estado (clave, valor, actualizado) VALUES ($1, $2::jsonb, now()) "
        "ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor, actualizado = now()",
        clave, json.dumps(valor, default=str))


async def sumar_flujo(db, por_hora: dict) -> None:
    """por_hora: {hora: {columna: total}} con columnas del flujo o de Rspamd."""
    columnas = COLUMNAS_FLUJO + COLUMNAS_RSPAMD
    for hora, cifras in por_hora.items():
        valores = [int(cifras.get(c, 0)) for c in columnas]
        if not any(valores):
            continue
        lista = ", ".join(columnas)
        marcas = ", ".join(f"${i + 2}" for i in range(len(columnas)))
        sumas = ", ".join(f"{c} = seg_flujo_hora.{c} + EXCLUDED.{c}" for c in columnas)
        await db.execute(
            f"INSERT INTO seg_flujo_hora (hora, {lista}) VALUES ($1, {marcas}) ON CONFLICT (hora) DO UPDATE SET {sumas}",
            hora, *valores)


async def anotar_cola(db, hora: datetime, tamano: int) -> None:
    await db.execute(
        "INSERT INTO seg_flujo_hora (hora, en_cola) VALUES ($1, $2) ON CONFLICT (hora) DO UPDATE SET en_cola = EXCLUDED.en_cola",
        hora, tamano)


async def sumar_accesos(db, filas: dict) -> set:
    """filas: {(hora, servicio, cuenta, ip): {"pais", "ok", "fallos"}}. Devuelve las horas tocadas."""
    horas = set()
    registros = []
    for (hora, servicio, cuenta, ip), v in filas.items():
        registros.append((hora, servicio, cuenta[:255], ip[:64], (v["pais"] or "--")[:8], int(v["ok"]), int(v["fallos"])))
        horas.add(hora)
    if registros:
        await db.executemany(
            "INSERT INTO seg_accesos_detalle (hora, servicio, cuenta, ip, pais, ok, fallos) VALUES ($1,$2,$3,$4,$5,$6,$7) "
            "ON CONFLICT (hora, servicio, cuenta, ip) DO UPDATE SET "
            "ok = CASE WHEN EXCLUDED.servicio = 'activesync' THEN GREATEST(seg_accesos_detalle.ok, EXCLUDED.ok) "
            "          ELSE seg_accesos_detalle.ok + EXCLUDED.ok END, "
            "fallos = seg_accesos_detalle.fallos + EXCLUDED.fallos, pais = EXCLUDED.pais",
            registros)
    return horas


async def recalcular_resumen(db, horas) -> None:
    """El resumen por hora, servicio y país sale del detalle (idempotente para las horas tocadas).
    Se llama dentro de la transacción de la pasada."""
    horas = sorted(horas)
    if not horas:
        return
    await db.execute("DELETE FROM seg_accesos_hora WHERE hora = ANY($1::timestamptz[])", horas)
    await db.execute(
        "INSERT INTO seg_accesos_hora (hora, servicio, pais, ok, fallos, cuentas, ips) "
        "SELECT hora, servicio, pais, sum(ok), sum(fallos), "
        "       count(DISTINCT cuenta) FILTER (WHERE ok > 0 AND cuenta <> ''), count(DISTINCT ip) "
        "  FROM seg_accesos_detalle WHERE hora = ANY($1::timestamptz[]) GROUP BY hora, servicio, pais",
        horas)


async def paises_conocidos(db, cuentas) -> dict:
    cuentas = sorted({c for c in cuentas if c})
    salida = {c: set() for c in cuentas}
    if cuentas:
        for f in await db.fetch("SELECT cuenta, pais FROM seg_cuenta_pais WHERE cuenta = ANY($1::text[])", cuentas):
            salida[f["cuenta"]].add(f["pais"])
    return salida


async def aprender_paises(db, eventos) -> None:
    vistos: dict = {}
    for e in eventos:
        if e.resultado == "ok" and e.cuenta and e.pais not in ("", "LAN", "--"):
            clave = (e.cuenta[:255], e.pais)
            n, ultimo = vistos.get(clave, (0, e.momento))
            vistos[clave] = (n + 1, max(ultimo, e.momento))
    if vistos:
        await db.executemany(
            "INSERT INTO seg_cuenta_pais (cuenta, pais, primera_vez, ultima_vez, accesos) VALUES ($1, $2, $3, $3, $4) "
            "ON CONFLICT (cuenta, pais) DO UPDATE SET ultima_vez = GREATEST(seg_cuenta_pais.ultima_vez, EXCLUDED.ultima_vez), "
            "accesos = seg_cuenta_pais.accesos + EXCLUDED.accesos",
            [(c, p, m, n) for (c, p), (n, m) in vistos.items()])


async def histograma(db, cuentas) -> dict:
    cuentas = sorted({c for c in cuentas if c})
    salida = {}
    if cuentas:
        for f in await db.fetch("SELECT cuenta, hora, accesos FROM seg_cuenta_hora WHERE cuenta = ANY($1::text[])", cuentas):
            salida.setdefault(f["cuenta"], [0] * 24)[int(f["hora"])] = int(f["accesos"])
    return salida


async def aprender_horas(db, eventos, zona, servicios) -> None:
    cuenta_hora: dict = {}
    for e in eventos:
        if e.resultado == "ok" and e.cuenta and e.servicio in servicios:
            clave = (e.cuenta[:255], e.momento.astimezone(zona).hour)
            cuenta_hora[clave] = cuenta_hora.get(clave, 0) + 1
    if cuenta_hora:
        await db.executemany(
            "INSERT INTO seg_cuenta_hora (cuenta, hora, accesos) VALUES ($1, $2, $3) "
            "ON CONFLICT (cuenta, hora) DO UPDATE SET accesos = seg_cuenta_hora.accesos + EXCLUDED.accesos",
            [(c, h, n) for (c, h), n in cuenta_hora.items()])


async def ips_con_muchas_cuentas(db, umbral: int) -> list:
    filas = await db.fetch(
        "SELECT ip, max(pais) AS pais, count(DISTINCT cuenta) AS cuentas, sum(fallos) AS fallos, "
        "       count(DISTINCT cuenta) FILTER (WHERE ok > 0) AS ok_cuentas "
        "  FROM seg_accesos_detalle "
        " WHERE hora >= date_trunc('hour', now()) - interval '1 hour' AND ip <> '' AND cuenta <> '' AND pais <> 'LAN' "
        " GROUP BY ip HAVING count(DISTINCT cuenta) >= $1", umbral)
    return [dict(f) for f in filas]


async def guardar_hallazgos(db, hallazgos) -> list:
    """Inserta los hallazgos nuevos; los repetidos (misma huella) solo suman. Devuelve los nuevos."""
    nuevos = []
    for h in hallazgos:
        fila = await db.fetchrow(
            "INSERT INTO seg_alertas (regla, severidad, cuenta, ip, pais, servicio, descripcion, detalles, huella, creada, ultima_vez) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$10) "
            "ON CONFLICT (huella) DO UPDATE SET repeticiones = seg_alertas.repeticiones + 1, ultima_vez = EXCLUDED.ultima_vez "
            "RETURNING id, (xmax = 0) AS nueva",
            h.regla, h.severidad, h.cuenta[:255], h.ip[:64], (h.pais or "")[:8], h.servicio[:16], h.descripcion,
            json.dumps(h.detalles, default=str), h.huella[:200], h.momento)
        if fila and fila["nueva"]:
            nuevos.append((fila["id"], h))
    return nuevos


async def depurar(db, cfg: dict) -> dict:
    """Retención: resúmenes y alertas cerradas a `retencion_dias`; detalle a `retencion_detalle_dias`."""
    dias, detalle = int(cfg["retencion_dias"]), int(cfg["retencion_detalle_dias"])
    borrados = {}
    for tabla, columna, d in (("seg_flujo_hora", "hora", dias), ("seg_accesos_hora", "hora", dias),
                              ("seg_accesos_detalle", "hora", detalle)):
        r = await db.execute(f"DELETE FROM {tabla} WHERE {columna} < now() - make_interval(days => $1)", d)
        borrados[tabla] = int(r.split()[-1]) if r else 0
    r = await db.execute(
        "DELETE FROM seg_alertas WHERE estado = 'cerrada' AND cerrada_en < now() - make_interval(days => $1)", dias)
    borrados["seg_alertas"] = int(r.split()[-1]) if r else 0
    return borrados
