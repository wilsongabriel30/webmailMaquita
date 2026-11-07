"""Cierre automático del buzón cuando Talento Humano registra la SALIDA en la nómina (05/11/2026).

Lo llama app/tareas/jefes.py en cada corrida (cada 10 min). Regla:
  - trabajador con estado «Desvinculado» y fecha de salida (últimos 90 días) y correo institucional;
  - el buzón sigue activo y ese correo NO está asignado a otra persona activa en la nómina;
  - no se ha cerrado ya por esa misma salida (tabla buzones_cerrados_salida).
Acción: contraseña nueva aleatoria (nadie la conoce; Sistemas la repone desde el panel si hace falta),
se cierran TODAS sus sesiones (webmail, app, Teams) y se borran sus contraseñas de aplicación.
El buzón NO se desactiva: sigue recibiendo correo para que se pueda reasignar.

Modo: SALIDAS_CERRAR_BUZON=1 en .env cierra de verdad; sin esa variable solo SIMULA (anota a quién
cerraría en el registro y en la tabla con modo='simulacion') para revisar antes de activarlo.
"""

import logging
import os
import secrets
import subprocess

import asyncpg

log = logging.getLogger("tareas.salidas")

DDL = """CREATE TABLE IF NOT EXISTS buzones_cerrados_salida (
    id SERIAL PRIMARY KEY, email TEXT NOT NULL, nombre TEXT NOT NULL DEFAULT '', fecha_salida DATE NOT NULL,
    modo TEXT NOT NULL, cerrado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE (email, fecha_salida, modo));"""

DIAS_VENTANA = 90


def _valor_env(clave: str) -> str:
    if os.getenv(clave):
        return os.getenv(clave)
    try:
        for l in open(".env", encoding="utf-8"):
            if l.startswith(clave + "="):
                return l.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def _hash_clave(clave: str) -> str:
    return subprocess.run(
        ["doveadm", "pw", "-s", "SHA512-CRYPT", "-p", clave],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    ).stdout.strip()


async def _desvinculados(dsn_nomina: str) -> list[dict]:
    nom = await asyncpg.connect(dsn_nomina)
    try:
        rows = await nom.fetch(
            """SELECT lower(trim(email_institucional)) AS email, trim(nombres||' '||apellidos) AS nombre, fecha_salida
               FROM trabajadores
               WHERE es_version_actual AND lower(coalesce(estado,'')) = 'desvinculado' AND fecha_salida IS NOT NULL
                 AND fecha_salida >= current_date - $1::int AND email_institucional ILIKE '%@%'
               ORDER BY fecha_salida DESC""",
            DIAS_VENTANA,
        )
    finally:
        await nom.close()
    return [dict(r) for r in rows]


async def procesar(db, activos_inst: set, dsn_nomina: str, es_institucional) -> dict:
    """`db`: conexión a maildb. `activos_inst`: correos institucionales con personal activo en la nómina."""
    await db.execute(DDL)
    cerrar = _valor_env("SALIDAS_CERRAR_BUZON") == "1"
    modo = "cerrado" if cerrar else "simulacion"
    resumen = {"modo": modo, "candidatos": [], "cerrados": 0}
    for s in await _desvinculados(dsn_nomina):
        email = s["email"]
        if not es_institucional(email) or email in activos_inst:
            continue  # correo no institucional, o ya reasignado a otra persona activa
        if not await db.fetchval(
            "SELECT 1 FROM mailbox WHERE lower(username) = $1 AND active", email
        ):
            continue  # buzón ya inactivo o inexistente
        if await db.fetchval(
            "SELECT 1 FROM buzones_cerrados_salida WHERE email = $1 AND fecha_salida = $2 AND modo = $3",
            email,
            s["fecha_salida"],
            modo,
        ):
            continue  # ya tratado
        resumen["candidatos"].append(
            f"{email} ({s['nombre']}, salida {s['fecha_salida']})"
        )
        if not cerrar:
            await db.execute(
                "INSERT INTO buzones_cerrados_salida (email, nombre, fecha_salida, modo) VALUES ($1,$2,$3,'simulacion') ON CONFLICT DO NOTHING",
                email,
                s["nombre"],
                s["fecha_salida"],
            )
            log.warning(
                "SIMULACION salida: cerraría el buzón %s (%s, salida %s)",
                email,
                s["nombre"],
                s["fecha_salida"],
            )
            continue
        # --- cierre real ---
        nueva = secrets.token_urlsafe(18)
        await db.execute(
            "UPDATE mailbox SET password = $1, modified = NOW() WHERE lower(username) = $2",
            _hash_clave(nueva),
            email,
        )
        for sql in (
            "DELETE FROM app_passwords WHERE lower(username) = $1",
            "DELETE FROM contrasenas_aplicacion WHERE lower(username) = $1",
        ):
            try:
                await db.execute(sql, email)
            except (
                Exception
            ):  # noqa: BLE001  (la tabla puede no existir con ese nombre)
                pass
        try:
            import redis.asyncio as redis_async

            from app.auth.sesiones import revocar_todo

            r = redis_async.from_url(_valor_env("REDIS_URL"))
            try:
                await revocar_todo(db, r, email, "salida de personal (nómina)")
            finally:
                await r.aclose()
        except Exception as e:  # noqa: BLE001
            log.error(
                "salida %s: contraseña cambiada pero no se pudieron cerrar las sesiones: %s",
                email,
                e,
            )
        await db.execute(
            "INSERT INTO buzones_cerrados_salida (email, nombre, fecha_salida, modo) VALUES ($1,$2,$3,'cerrado') ON CONFLICT DO NOTHING",
            email,
            s["nombre"],
            s["fecha_salida"],
        )
        resumen["cerrados"] += 1
        log.warning(
            "SALIDA: buzón %s cerrado (%s, salida %s): contraseña nueva, sesiones y claves de app revocadas",
            email,
            s["nombre"],
            s["fecha_salida"],
        )
    return resumen
