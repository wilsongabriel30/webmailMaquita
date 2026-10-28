-- Importancia (Alta o Baja) también en los envíos programados (28/10/2026).
-- La elige la persona en la cinta del redactor; «normal» no marca el correo.
-- Idempotente. Se aplica como el usuario de la aplicación (el de DATABASE_URL).
ALTER TABLE scheduled_emails ADD COLUMN IF NOT EXISTS importance text NOT NULL DEFAULT 'normal';
