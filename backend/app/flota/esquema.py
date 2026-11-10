"""Tablas de Flota Maquita (T-88). Se crean al arrancar, dentro del DDL serializado de `main.py`.

- `flota_equipos`: un equipo propio por `machine_guid`; `equipo_id` es estable (si se reinstala y se
  vuelve a enrolar con otro código, conserva el mismo id y se rota su secreto).
- `flota_codigos`: códigos de alta de un solo uso (solo su SHA-256). Los crea Tecnología en el panel.
- `flota_ordenes`: órdenes por equipo. `carga` son los bytes firmados (base64) y `firma` la firma
  ECDSA P-256 (r||s, base64). Se firman AL EMITIRLAS en el panel: el backend público no tiene la clave.
- `flota_registro`: bitácora de toda acción (panel, equipo y servidor). Solo admite INSERT.
"""

DDL = """
CREATE TABLE IF NOT EXISTS flota_codigos (
    id            BIGSERIAL PRIMARY KEY,
    codigo_hash   TEXT NOT NULL UNIQUE,
    prefijo       TEXT NOT NULL,
    etiqueta      TEXT NOT NULL DEFAULT '',
    creado_por    TEXT NOT NULL,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    caduca_en     TIMESTAMPTZ NOT NULL,
    usado_en      TIMESTAMPTZ,
    equipo_id     UUID,
    ip_uso        TEXT NOT NULL DEFAULT '',
    anulado_en    TIMESTAMPTZ,
    anulado_por   TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS flota_equipos (
    equipo_id      UUID PRIMARY KEY,
    machine_guid   UUID NOT NULL UNIQUE,
    nombre         TEXT NOT NULL DEFAULT '',
    etiqueta       TEXT NOT NULL DEFAULT '',
    secreto_hash   TEXT NOT NULL,
    estado         TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'retirado')),
    windows        TEXT NOT NULL DEFAULT '',
    version_app    TEXT NOT NULL DEFAULT '',
    inventario     JSONB,
    inventario_en  TIMESTAMPTZ,
    codigo_id      BIGINT,
    enrolado_en    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reenrolado_en  TIMESTAMPTZ,
    ultimo_sondeo  TIMESTAMPTZ,
    ultima_ip      TEXT NOT NULL DEFAULT '',
    retirado_en    TIMESTAMPTZ,
    retirado_por   TEXT NOT NULL DEFAULT '',
    motivo_retiro  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_flota_equipos_nombre ON flota_equipos (upper(nombre));
CREATE TABLE IF NOT EXISTS flota_ordenes (
    orden_id      UUID PRIMARY KEY,
    equipo_id     UUID NOT NULL REFERENCES flota_equipos (equipo_id),
    tipo          TEXT NOT NULL,
    parametros    JSONB NOT NULL DEFAULT '{}'::jsonb,
    kid           TEXT NOT NULL,
    carga         TEXT NOT NULL,
    firma         TEXT NOT NULL,
    emitida_por   TEXT NOT NULL,
    motivo        TEXT NOT NULL DEFAULT '',
    emitida_en    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    caduca_en     TIMESTAMPTZ NOT NULL,
    estado        TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN
                  ('pendiente', 'entregada', 'recibida', 'ejecutando', 'ok', 'error', 'rechazada', 'anulada')),
    entregas      INTEGER NOT NULL DEFAULT 0,
    entregada_en  TIMESTAMPTZ,
    resultado_en  TIMESTAMPTZ,
    registro      TEXT NOT NULL DEFAULT '',
    datos         JSONB,
    anulada_en    TIMESTAMPTZ,
    anulada_por   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_flota_ordenes_equipo ON flota_ordenes (equipo_id, emitida_en DESC);
CREATE INDEX IF NOT EXISTS ix_flota_ordenes_vivas ON flota_ordenes (equipo_id)
    WHERE estado IN ('pendiente', 'entregada');
CREATE TABLE IF NOT EXISTS flota_registro (
    id         BIGSERIAL PRIMARY KEY,
    momento    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    equipo_id  UUID,
    orden_id   UUID,
    actor      TEXT NOT NULL,
    accion     TEXT NOT NULL,
    detalle    JSONB,
    ip         TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_flota_registro_momento ON flota_registro (momento DESC);
CREATE INDEX IF NOT EXISTS ix_flota_registro_equipo ON flota_registro (equipo_id, momento DESC);
CREATE OR REPLACE FUNCTION flota_registro_solo_insertar() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'flota_registro es de solo inserción (auditoría LOPDP)';
END $$;
CREATE OR REPLACE TRIGGER tr_flota_registro_solo_insertar
    BEFORE UPDATE OR DELETE ON flota_registro
    FOR EACH ROW EXECUTE FUNCTION flota_registro_solo_insertar();
"""


async def asegurar_tablas(pool) -> None:
    await pool.execute(DDL)
