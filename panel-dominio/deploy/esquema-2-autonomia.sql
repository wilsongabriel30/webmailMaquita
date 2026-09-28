-- Portal de dominio, segunda entrega: segundo factor y solicitudes de eliminación.
ALTER TABLE pd_admins ADD COLUMN IF NOT EXISTS totp_secret TEXT;
ALTER TABLE pd_admins ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE pd_admins ADD COLUMN IF NOT EXISTS totp_last_step BIGINT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS pd_solicitudes (
    id SERIAL PRIMARY KEY,
    admin_id INT REFERENCES pd_admins(id) ON DELETE SET NULL,
    admin_username VARCHAR(255) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    objetivo VARCHAR(255) NOT NULL,
    dominio VARCHAR(255) NOT NULL,
    motivo TEXT NOT NULL DEFAULT '',
    estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
    resuelto_por VARCHAR(255),
    resuelto_en TIMESTAMP WITH TIME ZONE,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pd_solicitudes_estado ON pd_solicitudes(estado, creado_en DESC);
