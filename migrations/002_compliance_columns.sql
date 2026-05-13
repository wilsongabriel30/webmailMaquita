-- Migración 002: Columnas adicionales para correlación, GPG, RBAC
-- Ejecutar FUERA de transacción (cada ALTER es independiente)
-- Fecha: 2026-05-13
-- Idempotente: usa ADD COLUMN IF NOT EXISTS

-- mail_trace: correlación Dovecot
ALTER TABLE mail_trace ADD COLUMN IF NOT EXISTS dovecot_user VARCHAR(255);
ALTER TABLE mail_trace ADD COLUMN IF NOT EXISTS dovecot_folder VARCHAR(255);
ALTER TABLE mail_trace ADD COLUMN IF NOT EXISTS dovecot_event VARCHAR(50);
ALTER TABLE mail_trace ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ;

-- ediscovery_exports: firma GPG + timestamp
ALTER TABLE ediscovery_exports ADD COLUMN IF NOT EXISTS gpg_signature TEXT;
ALTER TABLE ediscovery_exports ADD COLUMN IF NOT EXISTS timestamp_token TEXT;

-- legal_holds: razón de liberación
ALTER TABLE legal_holds ADD COLUMN IF NOT EXISTS disable_reason TEXT;

-- fraud_alerts: campos mejorados
ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'open';
ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS related_message_id VARCHAR(500);
ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS related_case_id BIGINT;
ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS closed_by VARCHAR(255);
ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;

-- ediscovery_searches: flags de búsqueda
ALTER TABLE ediscovery_searches ADD COLUMN IF NOT EXISTS search_body BOOLEAN DEFAULT TRUE;
ALTER TABLE ediscovery_searches ADD COLUMN IF NOT EXISTS search_attachments BOOLEAN DEFAULT TRUE;

-- ediscovery_results: keywords encontradas
ALTER TABLE ediscovery_results ADD COLUMN IF NOT EXISTS matched_keywords TEXT[];

-- Índices adicionales
CREATE INDEX IF NOT EXISTS idx_mt_dovecot_user ON mail_trace(dovecot_user);
CREATE INDEX IF NOT EXISTS idx_mt_delivered ON mail_trace(delivered_at);
CREATE INDEX IF NOT EXISTS idx_fa_status ON fraud_alerts(status);
CREATE INDEX IF NOT EXISTS idx_fa_case ON fraud_alerts(related_case_id);
