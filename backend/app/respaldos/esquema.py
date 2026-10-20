"""Tablas de T-74. Se crean al arrancar (mismo patrón que telemetría y tareas).

- `respaldos_vinculos`: buzón de la persona ↔ cliente UrBackup. La carga soporte A MANO una vez
  (propuesta en T74-PROPUESTA-VINCULOS-20261020.csv); varias cuentas de la misma persona pueden apuntar
  al mismo cliente. `habilitado = false` marca cuentas que no deben pedir respaldo (servicio, pruebas).
- `respaldos_equipos`: `machine_guid` ↔ cliente. Lo rellena el primer canje; desde ahí manda el vínculo
  con el equipo, no el nombre del PC.
- `respaldos_codigos`: solo el SHA-256 del código, atado al `machine_guid`, 10 minutos, un uso.
"""

DDL = """
CREATE TABLE IF NOT EXISTS respaldos_vinculos (
    user_email     TEXT PRIMARY KEY,
    clientid       INTEGER,
    cliente        TEXT NOT NULL DEFAULT '',
    habilitado     BOOLEAN NOT NULL DEFAULT TRUE,
    nota           TEXT NOT NULL DEFAULT '',
    cargado_por    TEXT NOT NULL DEFAULT '',
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_respaldos_vinculos_cliente ON respaldos_vinculos (clientid);
CREATE TABLE IF NOT EXISTS respaldos_equipos (
    machine_guid  UUID PRIMARY KEY,
    user_email    TEXT NOT NULL,
    clientid      INTEGER,
    cliente       TEXT NOT NULL,
    equipo        TEXT NOT NULL DEFAULT '',
    app           TEXT NOT NULL DEFAULT '',
    primer_canje  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultimo_canje  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_respaldos_equipos_cliente ON respaldos_equipos (clientid);
CREATE TABLE IF NOT EXISTS respaldos_codigos (
    id             BIGSERIAL PRIMARY KEY,
    codigo_hash    TEXT NOT NULL UNIQUE,
    user_email     TEXT NOT NULL,
    machine_guid   UUID NOT NULL,
    equipo         TEXT NOT NULL DEFAULT '',
    app            TEXT NOT NULL DEFAULT '',
    clientid       INTEGER,
    cliente        TEXT NOT NULL,
    nuevo          BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    caduca_en      TIMESTAMPTZ NOT NULL,
    usado_en       TIMESTAMPTZ,
    anulado_en     TIMESTAMPTZ,
    motivo         TEXT NOT NULL DEFAULT '',
    ip_alta        TEXT NOT NULL DEFAULT '',
    ip_canje       TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_respaldos_codigos_usuario ON respaldos_codigos (user_email, creado_en DESC);
"""


async def asegurar_tablas(pool) -> None:
    await pool.execute(DDL)
