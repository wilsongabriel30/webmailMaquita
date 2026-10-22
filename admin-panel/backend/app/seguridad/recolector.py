"""Recolector de los tableros de seguridad: una pasada cada 5 minutos (maquita-seguridad-recolector.timer).

    python -m app.seguridad.recolector             # una pasada
    python -m app.seguridad.recolector --comprobar # solo dice qué fuentes encuentra (no escribe nada)

Lee lo nuevo desde la pasada anterior (registro del correo o diario de systemd, acceso de ActiveSync,
auditoría del webmail y del panel, estadísticas de Rspamd y tamaño de la cola), deja los totales por
hora en las tablas seg_*, aplica las reglas de anomalía, avisa por correo y aplica la retención.
Usa el mismo .env que el panel (DB_HOST, DB_USER, DB_PASS…), pero no necesita sus secretos de sesión.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import socket
import sys
import time
from collections import Counter
from datetime import datetime, timezone

from app import organizacion

from . import ajustes, almacen, anomalias, avisos, exportar, fuentes, parseo, zona
from .agregador import (REDES_PASARELA_DEFECTO, agregar_accesos, agregar_correo, delta_rspamd, filtro_pasarela,
                        hora_de)
from .geo import Geo

_log = logging.getLogger("seguridad.recolector")
CERROJO = 727110  # pg_try_advisory_lock: nunca dos pasadas a la vez
LOG_CORREO = os.getenv("SEG_LOG_CORREO", "/var/log/mail.log")
LOG_ACTIVESYNC = os.getenv("SEG_LOG_ACTIVESYNC", "/var/log/nginx/activesync-access.log")

_SQL_WEBMAIL = ("SELECT id, username, action, category, risk_level, ip_address, created_at FROM user_activity_log "
                "WHERE id > $1 AND (action IN ('login_success', 'login_failed', 'login_blocked') OR category = 'compliance') "
                "ORDER BY id LIMIT $2")
_SQL_WEBMAIL_INICIO = ("SELECT COALESCE(max(id), 0) FROM user_activity_log "
                       "WHERE created_at < now() - interval '1 day'")
_SQL_PANEL = ("SELECT id, admin_username, action, target, ip_address, created_at FROM admin_audit "
              "WHERE id > $1 ORDER BY id LIMIT $2")
_SQL_PANEL_INICIO = "SELECT COALESCE(max(id), 0) FROM admin_audit WHERE created_at < now() - interval '1 day'"


def _redes_pasarela() -> list:
    texto = os.getenv("SEG_REDES_PASARELA", "")
    return [t for t in texto.replace(",", " ").split() if t] or list(REDES_PASARELA_DEFECTO)


async def _rspamd() -> dict | None:
    import httpx

    url = os.getenv("RSPAMD_URL", "http://localhost:11334").rstrip("/")
    cabeceras = {"Password": os.environ["RSPAMD_PASSWORD"]} if os.getenv("RSPAMD_PASSWORD") else {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{url}/stat", headers=cabeceras)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        _log.warning("Rspamd /stat no respondió: %s", e)
        return None


def _a_eventos_previos(lista) -> list:
    salida = []
    for d in lista or []:
        try:
            salida.append(parseo.EventoAcceso(datetime.fromisoformat(d["m"]), "", "fallo", d["c"], d.get("ip", ""), int(d.get("v", 1))))
        except (KeyError, ValueError, TypeError):
            continue
    return salida


def _de_eventos(lista) -> list:
    return [{"m": e.momento.isoformat(), "c": e.cuenta, "ip": e.ip, "v": e.veces} for e in lista][-5000:]


async def _leer_registros(c, ahora, tz, resumen) -> list:
    eventos = []
    if os.path.isfile(LOG_CORREO) and os.path.getsize(LOG_CORREO) > 0:
        lineas, est = fuentes.leer_archivo(LOG_CORREO, await almacen.estado(c, "pos_correo"))
        await almacen.guardar_estado(c, "pos_correo", est)
        resumen["fuentes"]["correo"] = {"origen": LOG_CORREO, "lineas": len(lineas)}
    else:
        cursor = await almacen.estado(c, "cursor_diario")
        lineas, cursor = await asyncio.to_thread(fuentes.leer_diario, cursor)
        if cursor:
            await almacen.guardar_estado(c, "cursor_diario", cursor)
        resumen["fuentes"]["correo"] = {"origen": "journald", "lineas": len(lineas)}
    for linea in lineas:
        eventos.extend(parseo.analizar_linea(linea, ahora, tz))
    if os.path.isfile(LOG_ACTIVESYNC):
        lineas, est = fuentes.leer_archivo(LOG_ACTIVESYNC, await almacen.estado(c, "pos_activesync"))
        await almacen.guardar_estado(c, "pos_activesync", est)
        resumen["fuentes"]["activesync"] = {"origen": LOG_ACTIVESYNC, "lineas": len(lineas)}
        for linea in lineas:
            eventos.extend(parseo.analizar_activesync(linea))
    return eventos


async def _leer_auditoria(c, resumen) -> tuple:
    """Accesos del webmail y del panel, y lo que va al registro JSON de Wazuh."""
    eventos, json_eventos = [], []
    filas, ultimo = await fuentes.filas_nuevas(c, _SQL_WEBMAIL, await almacen.estado(c, "id_webmail"), _SQL_WEBMAIL_INICIO)
    await almacen.guardar_estado(c, "id_webmail", ultimo)
    for f in filas:
        e = parseo.evento_auditoria("webmail", f["action"], f["username"], f["ip_address"], f["created_at"])
        if e:
            eventos.append(e)
        if f["category"] == "compliance":
            json_eventos.append(exportar.evento_webmail(f))
    filas_p, ultimo = await fuentes.filas_nuevas(c, _SQL_PANEL, await almacen.estado(c, "id_panel"), _SQL_PANEL_INICIO)
    await almacen.guardar_estado(c, "id_panel", ultimo)
    for f in filas_p:
        e = parseo.evento_auditoria("panel", f["action"], f["admin_username"], f["ip_address"], f["created_at"])
        if e:
            eventos.append(e)
        json_eventos.append(exportar.evento_panel(f))
    resumen["fuentes"]["webmail"] = {"filas": len(filas)}
    resumen["fuentes"]["panel"] = {"filas": len(filas_p)}
    return eventos, json_eventos


async def _reglas(c, cfg, tz, accesos, ahora) -> list:
    cuentas = {e.cuenta for e in accesos if e.cuenta}
    hallazgos = []
    if cfg["regla_pais_nuevo"]:
        hallazgos += anomalias.regla_pais_nuevo(accesos, await almacen.paises_conocidos(c, cuentas))
    await almacen.aprender_paises(c, accesos)
    previos = _a_eventos_previos(await almacen.estado(c, "fallos_recientes", []))
    if cfg["regla_fallos_y_exito"]:
        h, conservar = anomalias.regla_fallos_y_exito(previos, accesos, cfg["umbral_fallos"], cfg["ventana_fallos_min"])
        hallazgos += h
        await almacen.guardar_estado(c, "fallos_recientes", _de_eventos(conservar))
    if cfg["regla_hora_inusual"]:
        hallazgos += anomalias.regla_hora_inusual(accesos, await almacen.histograma(c, cuentas), tz,
                                                  cfg["hora_min_historial"], cfg["hora_porcentaje_max"])
    await almacen.aprender_horas(c, accesos, tz, anomalias.SERVICIOS_INTERACTIVOS)
    if cfg["regla_muchas_cuentas_ip"]:
        filas = await almacen.ips_con_muchas_cuentas(c, cfg["umbral_cuentas_ip"])
        hallazgos += anomalias.regla_muchas_cuentas_ip(filas, cfg["umbral_cuentas_ip"], ahora)
    return await almacen.guardar_hallazgos(c, hallazgos)


async def _destinos(db) -> list:
    d = organizacion.lista("ORG_CORREOS_AVISOS")
    if not d:
        try:
            v = await db.fetchval("SELECT notify_admin FROM outbound_anomaly_config WHERE id = 1")
            d = [x for x in (v or "").replace(",", " ").split() if x]
        except Exception:
            d = []
    return d  # vacío: lib-avisos.sh decide (postmaster@dominio)


async def _avisar(db, cfg, nuevas, resumen) -> None:
    if not cfg["avisos"]:
        return
    servidor = socket.getfqdn()
    hora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
    cupo_estado = await almacen.estado(db, "avisos_hora")
    destinos = await _destinos(db)
    a_avisar = [(i, h) for i, h in nuevas if avisos.merece_aviso(h.severidad, cfg["aviso_severidad_minima"])]
    if a_avisar:
        puede, cupo_estado = avisos.cupo(cupo_estado, hora, cfg["avisos_por_hora"])
        if puede and avisos.enviar(*avisos.componer_resumen(a_avisar, servidor), destinos):
            await db.execute("UPDATE seg_alertas SET avisada = true WHERE id = ANY($1::bigint[])", [i for i, _ in a_avisar])
            resumen["avisos"] += 1
    if cfg["escalar_tras_horas"] > 0:
        pendientes = [dict(f) for f in await db.fetch(
            "SELECT id, descripcion, creada FROM seg_alertas WHERE estado = 'abierta' AND severidad = 'alta' "
            "AND escalada_en IS NULL AND creada < now() - make_interval(hours => $1) ORDER BY creada LIMIT 50",
            cfg["escalar_tras_horas"])]
        if pendientes:
            puede, cupo_estado = avisos.cupo(cupo_estado, hora, cfg["avisos_por_hora"])
            mas = organizacion.lista("ORG_CORREOS_ESCALAMIENTO")
            if puede and avisos.enviar(*avisos.componer_escalamiento(pendientes, cfg["escalar_tras_horas"], servidor),
                                       sorted(set(destinos + mas)) if (destinos or mas) else []):
                await db.execute("UPDATE seg_alertas SET escalada_en = now() WHERE id = ANY($1::bigint[])",
                                 [p["id"] for p in pendientes])
                resumen["escaladas"] += len(pendientes)
    await almacen.guardar_estado(db, "avisos_hora", cupo_estado)


async def pasada(pool, ahora: datetime | None = None) -> dict:
    t0 = time.monotonic()
    ahora = ahora or datetime.now(timezone.utc)
    resumen = {"inicio": ahora.isoformat(), "fuentes": {}, "avisos": 0, "escaladas": 0, "errores": []}
    cfg = await ajustes.leer(pool)
    tz = zona.zona(cfg["zona_horaria"])
    geo = Geo(organizacion.redes_propias())
    es_pasarela = filtro_pasarela(_redes_pasarela())
    async with pool.acquire() as c:
        async with c.transaction():
            eventos = await _leer_registros(c, ahora, tz, resumen)
            auditoria, json_eventos = await _leer_auditoria(c, resumen)
            eventos += auditoria
            accesos = []
            for e in eventos:
                if isinstance(e, parseo.EventoAcceso) and not es_pasarela(e):
                    accesos.append(parseo.EventoAcceso(e.momento, e.servicio, e.resultado, e.cuenta, e.ip, e.veces, geo.pais(e.ip)))
            flujo = agregar_correo(eventos)
            stat = await _rspamd()
            if stat is not None:
                delta = delta_rspamd(await almacen.estado(c, "rspamd"), stat)
                if delta:
                    flujo.setdefault(hora_de(ahora), Counter()).update(delta)
                await almacen.guardar_estado(c, "rspamd", {"scanned": stat.get("scanned"), "actions": stat.get("actions")})
            await almacen.sumar_flujo(c, flujo)
            cola = await asyncio.to_thread(fuentes.tamano_cola)
            if cola is not None:
                await almacen.anotar_cola(c, hora_de(ahora), cola)
            horas = await almacen.sumar_accesos(c, agregar_accesos(accesos))
            await almacen.recalcular_resumen(c, horas)
            nuevas = await _reglas(c, cfg, tz, accesos, ahora)
            resumen["borrados"] = await almacen.depurar(c, cfg)
        resumen.update({"eventos_correo": sum(sum(v.values()) for v in flujo.values()), "eventos_acceso": len(accesos),
                        "alertas_nuevas": len(nuevas), "cola": cola})
        try:
            await _avisar(c, cfg, nuevas, resumen)
        except Exception as e:  # un aviso que no sale no deshace lo recolectado
            resumen["errores"].append(f"avisos: {e}")
        if exportar.activo():
            try:
                exportar.escribir(json_eventos + [exportar.evento_alerta(i, h) for i, h in nuevas])
            except OSError as e:
                resumen["errores"].append(f"registro JSON: {e}")
        resumen["duracion_ms"] = int((time.monotonic() - t0) * 1000)
        resumen["fin"] = datetime.now(timezone.utc).isoformat()
        await almacen.guardar_estado(c, "ultima_pasada", resumen)
    return resumen


def comprobar() -> dict:
    """Qué fuentes encuentra este servidor (para el instalador y el ajuste 64). No escribe nada."""
    return {
        "registro_correo": LOG_CORREO if os.path.isfile(LOG_CORREO) else "journald",
        "activesync": LOG_ACTIVESYNC if os.path.isfile(LOG_ACTIVESYNC) else None,
        "geoip": os.path.isfile(os.getenv("GEOIP_DB", "/var/lib/GeoIP/dbip-city-lite.mmdb")),
        "avisos": os.path.isfile(avisos.LIB_AVISOS),
        "registro_json_wazuh": exportar.activo(),
        "zona_horaria": zona.del_servidor(),
    }


async def _principal() -> int:
    import asyncpg

    pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "maildb"), user=os.getenv("DB_USER", "mailserver"),
        password=os.getenv("DB_PASS", ""), min_size=1, max_size=2)
    try:
        async with pool.acquire() as cerrojo:
            if not await cerrojo.fetchval("SELECT pg_try_advisory_lock($1)", CERROJO):
                print("Otra pasada del recolector sigue en curso; se omite esta.")
                return 0
            try:
                resumen = await pasada(pool)
            finally:
                await cerrojo.execute("SELECT pg_advisory_unlock($1)", CERROJO)
        print(json.dumps(resumen, ensure_ascii=False, default=str))
        return 0
    finally:
        await pool.close()


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Recolector de los tableros de seguridad")
    p.add_argument("--comprobar", action="store_true", help="solo muestra las fuentes que encuentra")
    a = p.parse_args(argv)
    if a.comprobar:
        print(json.dumps(comprobar(), ensure_ascii=False))
        return 0
    return asyncio.run(_principal())


if __name__ == "__main__":
    sys.exit(main())
