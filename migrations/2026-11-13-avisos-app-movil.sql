-- Avisos de correo al instante para la app móvil, sin servicios de Google (AM-01, 13/11/2026).
-- Cada dispositivo registrado recibe un tema secreto del ntfy propio; al llegar un correo, el servidor
-- publica ahí un aviso sin contenido y la app, con su sesión, pide el detalle.
ALTER TABLE mobile_devices ADD COLUMN IF NOT EXISTS push_topic TEXT;
ALTER TABLE mobile_devices ADD COLUMN IF NOT EXISTS sid TEXT;
ALTER TABLE mobile_devices ADD COLUMN IF NOT EXISTS avisos BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE mobile_devices ADD COLUMN IF NOT EXISTS ultimo_aviso TIMESTAMPTZ;
ALTER TABLE mobile_devices ADD COLUMN IF NOT EXISTS avisos_enviados INTEGER NOT NULL DEFAULT 0;
CREATE UNIQUE INDEX IF NOT EXISTS mobile_devices_push_topic_uq ON mobile_devices (push_topic) WHERE push_topic IS NOT NULL;
CREATE INDEX IF NOT EXISTS mobile_devices_avisos_idx ON mobile_devices (lower(user_email)) WHERE is_active AND push_topic IS NOT NULL;
-- Un mismo teléfono puede tener varias cuentas (la app es multicuenta): la unicidad pasa de «teléfono» a
-- «teléfono y cuenta». Cada cuenta del teléfono tiene su propio tema.
ALTER TABLE mobile_devices DROP CONSTRAINT IF EXISTS mobile_devices_device_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS mobile_devices_telefono_cuenta_uq ON mobile_devices (device_id, user_email);
