# -*- coding: utf-8 -*-
"""Vista de sesiones para Tecnología (administradores) — L-04, 13/11/2026.

Todo dentro del propio servidor de correo (sin Raíces, sin mezclar sistemas). No da acceso
al contenido de los correos: solo metadatos de sesión. Registra en auditoría quién consulta
y quién cierra.
"""

import logging
import time

from app.auth.sesiones import LIMITE_SESIONES, listar_sesiones

log = logging.getLogger("seguridad.sesiones.admin")

UMBRAL_MUCHAS = 10  # cuentas con más de estas sesiones vivas salen en el resumen
SIN_USO_DIAS = 30


async def _usuarios_con_sesiones(redis):
    nombres = []
    try:
        async for clave in redis.scan_iter(match="sids:*", count=200):
            clave = clave.decode() if isinstance(clave, bytes) else clave
            nombres.append(clave[len("sids:") :])
    except Exception as exc:
        log.error("ADMIN_SESIONES_SCAN_FALLO error=%s", str(exc)[:120])
    return nombres


async def listar_todas(redis, persona=None, clase=None, antiguedad_dias=None) -> list:
    """Sesiones de TODAS las cuentas (con el username), filtrables por persona, clase y
    antigüedad de último uso."""
    persona = (persona or "").strip().lower()
    ahora = int(time.time())
    corte = (ahora - int(antiguedad_dias) * 86400) if antiguedad_dias else None
    salida = []
    for username in await _usuarios_con_sesiones(redis):
        if persona and persona not in username.lower():
            continue
        for ses in await listar_sesiones(redis, username):
            if clase and ses.get("clase") != clase:
                continue
            if (
                corte is not None
                and (ses.get("ultimo_uso") or ses.get("creada") or 0) > corte
            ):
                continue
            ses = dict(ses)
            ses["username"] = username
            salida.append(ses)
    salida.sort(key=lambda x: x.get("ultimo_uso") or x.get("creada") or 0, reverse=True)
    return salida


async def resumen(redis) -> dict:
    """Panorama: cuentas con muchas sesiones, sesiones sin uso prolongado, apps por versión."""
    ahora = int(time.time())
    corte = ahora - SIN_USO_DIAS * 86400
    muchas, sin_uso, por_version = [], 0, {}
    total = 0
    for username in await _usuarios_con_sesiones(redis):
        sesiones = await listar_sesiones(redis, username)
        total += len(sesiones)
        if len(sesiones) > UMBRAL_MUCHAS:
            muchas.append({"username": username, "sesiones": len(sesiones)})
        for ses in sesiones:
            if (ses.get("ultimo_uso") or ses.get("creada") or 0) < corte:
                sin_uso += 1
            if (ses.get("clase") or "").startswith("app"):
                v = (
                    ses.get("dispositivo") or ""
                )  # la versión va en el nombre; se usa app_version si está
                ver = ses.get("app_version") or ""
                etiqueta = ver or "sin versión"
                por_version[etiqueta] = por_version.get(etiqueta, 0) + 1
    muchas.sort(key=lambda x: x["sesiones"], reverse=True)
    return {
        "total_sesiones": total,
        "cuentas_con_muchas_sesiones": muchas,
        "umbral_muchas": UMBRAL_MUCHAS,
        "limite_por_cuenta": LIMITE_SESIONES,
        "sesiones_sin_uso_30_dias": sin_uso,
        "sin_uso_30_dias": sin_uso,
        "app_por_version": por_version,
    }


# -------------------------------------------------------------------- auditoría
async def asegurar_tabla_auditoria(db) -> None:
    await db.execute("""CREATE TABLE IF NOT EXISTS auth_sesiones_auditoria (
               id BIGSERIAL PRIMARY KEY,
               admin TEXT NOT NULL,
               accion TEXT NOT NULL,
               objetivo TEXT,
               detalle TEXT,
               cuando TIMESTAMPTZ NOT NULL DEFAULT now())""")


async def registrar_auditoria(
    db, admin: str, accion: str, objetivo: str = "", detalle: str = ""
) -> None:
    """Deja constancia de quién consultó o cerró qué. Nunca rompe la operación principal."""
    try:
        await db.execute(
            "INSERT INTO auth_sesiones_auditoria (admin, accion, objetivo, detalle) "
            "VALUES ($1, $2, $3, $4)",
            admin,
            accion,
            objetivo[:200],
            detalle[:500],
        )
    except Exception as exc:
        log.error(
            "ADMIN_SESIONES_AUDITORIA_FALLO admin=%s accion=%s error=%s",
            admin,
            accion,
            str(exc)[:120],
        )
    log.info("ADMIN_SESIONES admin=%s accion=%s objetivo=%s", admin, accion, objetivo)
