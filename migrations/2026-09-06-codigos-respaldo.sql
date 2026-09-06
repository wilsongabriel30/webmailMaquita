-- H-03 (cuarta revisión) / F-09 (tercera): códigos de respaldo de 2FA con 128 bits,
-- hash con sal, un código por fila y consumo atómico. Idempotente.
-- Se aplica ANTES de reiniciar el backend que lo usa.

CREATE TABLE IF NOT EXISTS user_totp_backup_codes (
    id         bigserial PRIMARY KEY,
    username   varchar(255) NOT NULL,
    sal        text         NOT NULL,
    code_hash  text         NOT NULL,
    created_at timestamptz  NOT NULL DEFAULT now(),
    used_at    timestamptz
);
CREATE INDEX IF NOT EXISTS user_totp_backup_codes_username
    ON user_totp_backup_codes (username) WHERE used_at IS NULL;

-- Los códigos anteriores (32 bits, en claro) dejan de valer: se vacían de la base.
-- Cada persona con 2FA genera unos nuevos desde Ajustes → Autenticación de dos factores.
UPDATE user_totp SET backup_codes = '{}'
 WHERE backup_codes IS NOT NULL AND array_length(backup_codes, 1) > 0;
