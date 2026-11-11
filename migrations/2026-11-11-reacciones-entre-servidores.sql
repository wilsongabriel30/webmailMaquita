-- Nombre visible de quien reacciona desde otro servidor de la suite (aquí no tiene buzón). Idempotente.
ALTER TABLE mail_reacciones ADD COLUMN IF NOT EXISTS nombre text;
