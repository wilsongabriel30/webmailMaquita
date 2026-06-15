-- Safe Attachments: dejar activo con CDR básico al instalar. Idempotente.
ALTER TABLE safeattach_config ADD COLUMN IF NOT EXISTS cdr_enabled boolean DEFAULT true;
UPDATE safeattach_config SET enabled=true, cdr_enabled=true, quarantine_suspicious=true WHERE id=1;
