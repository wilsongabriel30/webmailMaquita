-- Deteccion de macros en adjuntos Office en el milter de entrega (cabecera
-- X-Macro-Attachment). Default OFF, deteccion fail-open (no bloquea la entrega).
ALTER TABLE safeattach_config ADD COLUMN IF NOT EXISTS milter_attach_scan boolean NOT NULL DEFAULT false;
