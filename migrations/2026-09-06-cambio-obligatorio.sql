-- H-01 (cuarta revision): cambio de contrasena obligatorio por usuario, sin clave conocida en el codigo.
ALTER TABLE auth_estado ADD COLUMN IF NOT EXISTS must_change_password boolean NOT NULL DEFAULT false;
