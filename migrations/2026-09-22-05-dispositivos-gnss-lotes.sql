-- Teléfonos institucionales (22/09/2026): lotes de mediciones GNSS crudas (etapa 3, experimento de
-- corrección diferencial con la red REGME del IGM para las mediciones de campo de los técnicos).
-- El archivo va al disco (DISP_GNSS_DIR); aquí queda el índice y el resultado del procesamiento.
CREATE TABLE IF NOT EXISTS disp_gnss_lotes (
    id           SERIAL PRIMARY KEY,
    equipo_id    INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    recibido_en  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    inicio       VARCHAR(40),
    fin          VARCHAR(40),
    segundos     INT NOT NULL,
    formato      VARCHAR(32) NOT NULL DEFAULT 'gnsslogger-txt',
    modelo       VARCHAR(120),
    android      VARCHAR(40),
    capacidades  JSONB NOT NULL DEFAULT '{}'::jsonb,
    fix          JSONB,                       -- posición que calculó el propio teléfono, para comparar
    archivo      TEXT NOT NULL,
    bytes        INT NOT NULL,
    ip           VARCHAR(64),
    procesado_en TIMESTAMPTZ,
    resultado    JSONB                        -- {lat, lon, precision_m, estacion_regme, modo, notas}
);
CREATE INDEX IF NOT EXISTS disp_gnss_lotes_equipo ON disp_gnss_lotes (equipo_id, recibido_en DESC);
