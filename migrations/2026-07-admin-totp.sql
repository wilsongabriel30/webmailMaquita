-- 2FA (TOTP) para administradores del panel admin
-- Aplicar en la BD del panel: psql ... -f 2026-07-admin-totp.sql
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS totp_secret TEXT;
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT FALSE;
