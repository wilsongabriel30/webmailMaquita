-- Protección de salida: tablas del detector de envío masivo (cuenta comprometida).
-- Estaban creadas a mano en la instalación de origen y no venían en el repositorio, así que
-- una instalación nueva no las tenía (reportado por Andes, 03/10/2026). Idempotente.
-- Se aplica como el usuario de la aplicación (el de DATABASE_URL).

CREATE TABLE IF NOT EXISTS outbound_anomaly_config (
    id                   integer      PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    enabled              boolean      NOT NULL DEFAULT true,
    window_minutes       integer      NOT NULL DEFAULT 10,
    threshold_recipients integer      NOT NULL DEFAULT 30,
    action               varchar(10)  NOT NULL DEFAULT 'lock',
    -- A quién se avisa. Vacío: el detector usa ORG_CORREOS_AVISOS de organizacion.env.
    notify_admin         varchar(255) NOT NULL DEFAULT '',
    updated_at           timestamptz  DEFAULT now()
);
INSERT INTO outbound_anomaly_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS outbound_anomaly_events (
    id             bigserial    PRIMARY KEY,
    username       varchar(255) NOT NULL,
    recipients     integer      NOT NULL,
    messages       integer      NOT NULL,
    window_minutes integer      NOT NULL,
    action         varchar(16)  NOT NULL,
    detail         text,
    created_at     timestamptz  DEFAULT now()
);
-- Los índices se crean solo si faltan, comprobándolo antes: «CREATE INDEX IF NOT EXISTS» exige
-- ser dueño de la tabla aunque el índice ya exista, y en la instalación de origen estas tablas
-- se crearon a mano con otro usuario.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'idx_oae_created') THEN
        CREATE INDEX idx_oae_created ON outbound_anomaly_events (created_at DESC);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'idx_oae_user') THEN
        CREATE INDEX idx_oae_user ON outbound_anomaly_events (username, created_at DESC);
    END IF;
END $$;

-- Anti-suplantación: los términos de marca por omisión eran los de la organización que
-- desarrolla. En otra instalación ponían en cuarentena a cualquier remitente externo con esa
-- palabra en el nombre. El valor por omisión pasa a vacío; NO se tocan las filas existentes
-- (cada instalación conserva los términos que ya tenga y los revisa desde el panel).
ALTER TABLE IF EXISTS security_config ALTER COLUMN impersonation_terms SET DEFAULT '{}';
