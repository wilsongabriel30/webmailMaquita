-- F-01 / F-04 (tercera revisión ASVS): ciclo de vida de sesión con sid + auth_version.
-- Idempotente. Se aplica ANTES de reiniciar el backend que lo usa.

CREATE TABLE IF NOT EXISTS auth_estado (
    username     varchar(255) PRIMARY KEY,
    auth_version integer      NOT NULL DEFAULT 1,
    updated_at   timestamptz  NOT NULL DEFAULT now()
);

ALTER TABLE refresh_tokens
    ADD COLUMN IF NOT EXISTS sid                 varchar(32),
    ADD COLUMN IF NOT EXISTS session_kind        varchar(16) NOT NULL DEFAULT 'normal',
    ADD COLUMN IF NOT EXISTS absolute_expires_at timestamptz,
    ADD COLUMN IF NOT EXISTS auth_version        integer     NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS refresh_tokens_usuario_activos
    ON refresh_tokens (username) WHERE NOT is_revoked;
CREATE INDEX IF NOT EXISTS refresh_tokens_sid
    ON refresh_tokens (sid) WHERE sid IS NOT NULL;

-- Los refresh emitidos antes del modelo no tienen sid: no se pueden renovar (el código
-- los rechaza), así que se marcan revocados para no dejar filas «vivas» engañosas.
UPDATE refresh_tokens SET is_revoked = true WHERE sid IS NULL AND is_revoked = false;

-- La aplicación se conecta como mailserver: sin esto la tabla nueva no se puede leer.
GRANT SELECT, INSERT, UPDATE ON auth_estado TO mailserver;
