-- Preferencias de la cinta «Vista» guardadas en la cuenta (antes solo en el navegador). Idempotente.
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS vista jsonb NOT NULL DEFAULT '{}'::jsonb;
