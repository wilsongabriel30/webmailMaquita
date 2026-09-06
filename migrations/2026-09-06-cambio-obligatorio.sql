-- H-01 (cuarta revision): cambio de contrasena obligatorio por usuario, sin clave conocida en el codigo.
-- Autosuficiente: por orden alfabetico corre ANTES que 2026-09-06-sesiones-sid-av.sql, que tambien
-- crea auth_estado (ambas son idempotentes).
CREATE TABLE IF NOT EXISTS auth_estado (
    username     varchar(255) PRIMARY KEY,
    auth_version integer      NOT NULL DEFAULT 1,
    updated_at   timestamptz  NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE ON auth_estado TO mailserver;
ALTER TABLE auth_estado ADD COLUMN IF NOT EXISTS must_change_password boolean NOT NULL DEFAULT false;
