-- =============================================================================
-- Maquita Webmail — Migración inicial de tablas propias del backend
-- Generado: 2026-04-12 (Fase 3 limpieza)
-- Ejecutar: sudo -u postgres psql -d maildb -f init_tables.sql
-- =============================================================================

-- Labels (etiquetas de usuario)
CREATE TABLE IF NOT EXISTS user_labels (
    id SERIAL PRIMARY KEY,
    owner VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(7) NOT NULL DEFAULT '#0078d4',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(owner, name)
);
CREATE INDEX IF NOT EXISTS idx_labels_owner ON user_labels(owner);

CREATE TABLE IF NOT EXISTS message_labels (
    id SERIAL PRIMARY KEY,
    owner VARCHAR(255) NOT NULL,
    folder VARCHAR(255) NOT NULL,
    message_uid INTEGER NOT NULL,
    label_id INTEGER NOT NULL REFERENCES user_labels(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(owner, folder, message_uid, label_id)
);
CREATE INDEX IF NOT EXISTS idx_mlabels_owner_folder ON message_labels(owner, folder);

-- Scheduled emails (envío programado)
CREATE TABLE IF NOT EXISTS scheduled_emails (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    to_list JSONB NOT NULL DEFAULT '[]'::jsonb,
    cc_list JSONB NOT NULL DEFAULT '[]'::jsonb,
    bcc_list JSONB NOT NULL DEFAULT '[]'::jsonb,
    subject TEXT NOT NULL DEFAULT '',
    html_body TEXT NOT NULL DEFAULT '',
    text_body TEXT NOT NULL DEFAULT '',
    in_reply_to TEXT NOT NULL DEFAULT '',
    "references" TEXT NOT NULL DEFAULT '',
    scheduled_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_read_receipt BOOLEAN NOT NULL DEFAULT FALSE,
    request_delivery_receipt BOOLEAN NOT NULL DEFAULT FALSE
);

-- Email templates (plantillas)
CREATE TABLE IF NOT EXISTS email_templates (
    id SERIAL PRIMARY KEY,
    owner VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) DEFAULT '',
    subject VARCHAR(500) DEFAULT '',
    html_body TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_templates_owner ON email_templates(owner);

-- Snoozed emails (posponer)
CREATE TABLE IF NOT EXISTS snoozed_emails (
    id SERIAL PRIMARY KEY,
    owner VARCHAR(255) NOT NULL,
    original_folder VARCHAR(255) NOT NULL,
    original_uid INTEGER NOT NULL,
    snoozed_uid INTEGER,
    snooze_until TIMESTAMP NOT NULL,
    subject VARCHAR(500),
    from_addr VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    restored BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_snooze_owner ON snoozed_emails(owner);
CREATE INDEX IF NOT EXISTS idx_snooze_until ON snoozed_emails(snooze_until) WHERE restored = FALSE;

-- Priority cache (clasificación IA)
CREATE TABLE IF NOT EXISTS priority_cache (
    id SERIAL PRIMARY KEY,
    owner TEXT NOT NULL,
    folder TEXT NOT NULL,
    message_uid INT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal',
    category TEXT NOT NULL DEFAULT 'other',
    confidence REAL DEFAULT 0.5,
    reason TEXT DEFAULT '',
    classified_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(owner, folder, message_uid)
);
CREATE INDEX IF NOT EXISTS idx_priority_owner ON priority_cache(owner, folder);

-- Spam analysis (SpamGuard IA)
CREATE TABLE IF NOT EXISTS spam_analysis (
    id SERIAL PRIMARY KEY,
    owner TEXT NOT NULL,
    folder TEXT NOT NULL,
    message_uid INT NOT NULL,
    is_spam BOOLEAN NOT NULL DEFAULT false,
    spam_score INT NOT NULL DEFAULT 0,
    method TEXT NOT NULL DEFAULT 'heuristic',
    reasons TEXT[] DEFAULT ARRAY[]::TEXT[],
    analyzed_at TIMESTAMPTZ DEFAULT now(),
    user_override TEXT DEFAULT NULL,
    UNIQUE(owner, folder, message_uid)
);
CREATE INDEX IF NOT EXISTS idx_spam_owner ON spam_analysis(owner, folder);

-- TOTP (autenticación 2FA)
CREATE TABLE IF NOT EXISTS user_totp (
    username TEXT PRIMARY KEY,
    secret TEXT NOT NULL,
    enabled BOOLEAN DEFAULT FALSE,
    backup_codes TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    verified_at TIMESTAMPTZ
);
