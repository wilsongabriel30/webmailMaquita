# -*- coding: utf-8 -*-
"""DDL de arranque serializado entre workers.

El almacén arranca con 6 workers de gunicorn y cada uno ejecuta al importar la aplicación
varios `CREATE TABLE / ALTER TABLE ... IF NOT EXISTS` (esquema del motor, reservas de cuota,
directorio, cuentas externas, alias). Seis procesos haciendo DDL a la vez sobre las mismas
tablas provocaban `DeadlockDetected` (31 en 30 días): un worker moría y systemd relanzaba el
servicio.

`serializado()` toma un bloqueo consultivo de SESIÓN en una conexión aparte y lo suelta al
salir: un solo proceso hace el DDL a la vez; los demás esperan (milisegundos) y encuentran
todo creado. Es aparte de las conexiones que usan las funciones de DDL, así que no importa
que cada una abra su propia transacción.

Detrás de PgBouncer en modo «transaction» (PGBOUNCER=true) un bloqueo de sesión no sirve:
el desbloqueo puede ir a otra conexión del servidor y el bloqueo quedaría tomado. En ese
modo se usa `pg_advisory_xact_lock` dentro de una transacción abierta mientras dura el
bloque: se suelta solo con el commit (o si la conexión se corta).
"""
import logging
import os
from contextlib import contextmanager

log = logging.getLogger("almacen.ddl_arranque")

CLAVE_BLOQUEO = 815000


def con_pgbouncer() -> bool:
    return os.getenv("PGBOUNCER", "").strip().lower() in ("1", "true", "yes", "si", "sí")


@contextmanager
def _serializado_transaccion(pool, con, clave: int):
    """Variante para PgBouncer: el bloqueo vive lo que vive la transacción."""
    autocommit_previo = getattr(con, "autocommit", False)
    try:
        con.autocommit = False
        with con.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (clave,))
        try:
            yield
        finally:
            try:
                con.commit()
            except Exception as exc:
                log.warning("No se pudo cerrar la transacción del bloqueo de DDL (%s)", exc)
                try:
                    con.rollback()
                except Exception:
                    pass
    finally:
        try:
            con.autocommit = autocommit_previo
            pool.putconn(con)
        except Exception:
            pass


@contextmanager
def serializado(obtener_pool, clave: int = CLAVE_BLOQUEO):
    """Ejecuta el bloque con el bloqueo consultivo `clave` tomado en una conexión propia."""
    pool = obtener_pool()
    con = pool.getconn()
    if con_pgbouncer():
        with _serializado_transaccion(pool, con, clave):
            yield
        return
    autocommit_previo = getattr(con, "autocommit", False)
    try:
        con.autocommit = True
        with con.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (clave,))
        try:
            yield
        finally:
            try:
                with con.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (clave,))
            except Exception as exc:  # la sesión se cierra igual y el bloqueo cae con ella
                log.warning("No se pudo soltar el bloqueo de DDL (%s); se libera al devolver la conexión", exc)
    finally:
        try:
            con.autocommit = autocommit_previo
            pool.putconn(con)
        except Exception:
            pass
