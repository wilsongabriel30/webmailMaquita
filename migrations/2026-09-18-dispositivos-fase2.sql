-- Teléfonos institucionales, fase 2: ubicación (periódica, bajo demanda, avistamientos) y modo perdido.
-- La ubicación periódica solo se guarda si el custodio firmó la política (ubicacion_autorizada) o si
-- el equipo está declarado perdido. Ver docs/DISPOSITIVOS.md.

ALTER TABLE disp_equipos
    ADD COLUMN IF NOT EXISTS ubicacion_autorizada BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS politica_firmada_en  DATE,
    ADD COLUMN IF NOT EXISTS perdido_en           TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS perdido_motivo       VARCHAR(255),
    ADD COLUMN IF NOT EXISTS perdido_mensaje      VARCHAR(255),
    ADD COLUMN IF NOT EXISTS perdido_telefono     VARCHAR(40),
    ADD COLUMN IF NOT EXISTS baliza_id            CHAR(16);
CREATE UNIQUE INDEX IF NOT EXISTS disp_equipos_baliza ON disp_equipos (baliza_id) WHERE baliza_id IS NOT NULL;

ALTER TABLE disp_comandos ADD COLUMN IF NOT EXISTS motivo VARCHAR(255);

CREATE TABLE IF NOT EXISTS disp_ubicaciones (
    id          BIGSERIAL PRIMARY KEY,
    equipo_id   INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    tomada_en   TIMESTAMPTZ NOT NULL,
    recibida_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lat         DOUBLE PRECISION NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon         DOUBLE PRECISION NOT NULL CHECK (lon BETWEEN -180 AND 180),
    precision_m REAL,
    fuente      VARCHAR(12),
    origen      VARCHAR(14) NOT NULL DEFAULT 'periodica' CHECK (origen IN ('periodica', 'comando', 'perdido', 'avistamiento')),
    bateria     SMALLINT,
    visto_por   INT REFERENCES disp_equipos(id) ON DELETE SET NULL,   -- avistamiento: qué equipo lo oyó
    rssi        SMALLINT,
    ip          VARCHAR(64)
);
CREATE INDEX IF NOT EXISTS disp_ubicaciones_equipo ON disp_ubicaciones (equipo_id, tomada_en DESC);

UPDATE disp_config SET valor = valor || '{"version": 2, "ubicacion_minutos": 15, "latido_minutos_perdido": 5, "retencion_ubicaciones_dias": 90, "retencion_latidos_dias": 30}'::jsonb,
       actualizado_en = NOW()
 WHERE clave = 'politica' AND NOT (valor ? 'ubicacion_minutos');
