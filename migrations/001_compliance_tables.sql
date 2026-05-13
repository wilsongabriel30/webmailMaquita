-- ============================================================================
-- Compliance Module - Clean Migration
-- Purpose: Idempotent migration for all 8 compliance tables
-- Version: 2.0
-- Date: 2026-05-13
-- Notes: Replaces previous pg_dump-style migration. Safe to run multiple times.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. user_activity_log
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_activity_log (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(255) NOT NULL,
    action          VARCHAR(50) NOT NULL,
    category        VARCHAR(30) NOT NULL DEFAULT 'general',
    message_id      VARCHAR(255),
    mailbox         VARCHAR(255),
    folder          VARCHAR(255),
    target          VARCHAR(500),
    ip_address      INET,
    user_agent      TEXT,
    details         JSONB,
    risk_level      VARCHAR(10) DEFAULT 'low',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ual_username   ON user_activity_log (username);
CREATE INDEX IF NOT EXISTS idx_ual_action     ON user_activity_log (action);
CREATE INDEX IF NOT EXISTS idx_ual_category   ON user_activity_log (category);
CREATE INDEX IF NOT EXISTS idx_ual_created_at ON user_activity_log (created_at);
CREATE INDEX IF NOT EXISTS idx_ual_risk_level ON user_activity_log (risk_level);
CREATE INDEX IF NOT EXISTS idx_ual_message_id ON user_activity_log (message_id);

-- ============================================================================
-- 2. mail_trace
-- ============================================================================
CREATE TABLE IF NOT EXISTS mail_trace (
    id              BIGSERIAL PRIMARY KEY,
    queue_id        VARCHAR(20),
    message_id      VARCHAR(500),
    direction       VARCHAR(10) NOT NULL DEFAULT 'inbound',
    sender          VARCHAR(255),
    recipient       VARCHAR(255),
    subject_hash    VARCHAR(64),
    source_ip       INET,
    destination_mx  VARCHAR(255),
    helo_name       VARCHAR(255),
    size_bytes      BIGINT,
    spf_result      VARCHAR(20),
    dkim_result     VARCHAR(20),
    dmarc_result    VARCHAR(20),
    rspamd_score    REAL,
    rspamd_action   VARCHAR(30),
    status          VARCHAR(20) NOT NULL DEFAULT 'unknown',
    dsn             VARCHAR(10),
    delay_seconds   REAL,
    relay           VARCHAR(255),
    tls_version     VARCHAR(20),
    tls_cipher      VARCHAR(100),
    raw_log         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Dovecot correlation columns
    dovecot_user    VARCHAR(255),
    dovecot_folder  VARCHAR(255),
    dovecot_event   VARCHAR(50),
    delivered_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mt_queue_id   ON mail_trace (queue_id);
CREATE INDEX IF NOT EXISTS idx_mt_message_id ON mail_trace (message_id);
CREATE INDEX IF NOT EXISTS idx_mt_sender     ON mail_trace (sender);
CREATE INDEX IF NOT EXISTS idx_mt_recipient  ON mail_trace (recipient);
CREATE INDEX IF NOT EXISTS idx_mt_source_ip  ON mail_trace (source_ip);
CREATE INDEX IF NOT EXISTS idx_mt_status     ON mail_trace (status);
CREATE INDEX IF NOT EXISTS idx_mt_direction  ON mail_trace (direction);
CREATE INDEX IF NOT EXISTS idx_mt_created_at ON mail_trace (created_at);

-- Safe addition of Dovecot columns if table already existed without them
DO $$ BEGIN
    ALTER TABLE mail_trace ADD COLUMN IF NOT EXISTS dovecot_user   VARCHAR(255);
    ALTER TABLE mail_trace ADD COLUMN IF NOT EXISTS dovecot_folder VARCHAR(255);
    ALTER TABLE mail_trace ADD COLUMN IF NOT EXISTS dovecot_event  VARCHAR(50);
    ALTER TABLE mail_trace ADD COLUMN IF NOT EXISTS delivered_at   TIMESTAMPTZ;
END $$;

-- ============================================================================
-- 3. compliance_cases
-- ============================================================================
CREATE TABLE IF NOT EXISTS compliance_cases (
    id              BIGSERIAL PRIMARY KEY,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    reason          TEXT NOT NULL,
    case_type       VARCHAR(50) NOT NULL DEFAULT 'investigation',
    priority        VARCHAR(20) DEFAULT 'normal',
    status          VARCHAR(30) NOT NULL DEFAULT 'open',
    assigned_to     VARCHAR(255),
    created_by      VARCHAR(255) NOT NULL,
    approved_by     VARCHAR(255),
    authorized_by   VARCHAR(255),
    approved_at     TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ,
    close_reason    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cc_status     ON compliance_cases (status);
CREATE INDEX IF NOT EXISTS idx_cc_created_by ON compliance_cases (created_by);
CREATE INDEX IF NOT EXISTS idx_cc_created_at ON compliance_cases (created_at);

-- ============================================================================
-- 4. ediscovery_searches
-- ============================================================================
CREATE TABLE IF NOT EXISTS ediscovery_searches (
    id                  BIGSERIAL PRIMARY KEY,
    case_id             BIGINT NOT NULL REFERENCES compliance_cases(id),
    query_text          TEXT NOT NULL,
    mailboxes_scope     TEXT[] DEFAULT '{}',
    date_from           TIMESTAMPTZ,
    date_to             TIMESTAMPTZ,
    keywords            TEXT[] DEFAULT '{}',
    folders             TEXT[] DEFAULT '{}',
    search_body         BOOLEAN DEFAULT TRUE,
    search_attachments  BOOLEAN DEFAULT TRUE,
    status              VARCHAR(30) DEFAULT 'pending',
    results_count       INTEGER DEFAULT 0,
    searched_by         VARCHAR(255) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_es_case_id     ON ediscovery_searches (case_id);
CREATE INDEX IF NOT EXISTS idx_es_searched_by ON ediscovery_searches (searched_by);

-- ============================================================================
-- 5. ediscovery_results
-- ============================================================================
CREATE TABLE IF NOT EXISTS ediscovery_results (
    id                BIGSERIAL PRIMARY KEY,
    search_id         BIGINT NOT NULL REFERENCES ediscovery_searches(id),
    mailbox           VARCHAR(255) NOT NULL,
    folder            VARCHAR(255),
    uid               INTEGER,
    message_id        VARCHAR(500),
    subject           TEXT,
    sender            VARCHAR(255),
    recipients        TEXT,
    sent_at           TIMESTAMPTZ,
    size_bytes        BIGINT,
    has_attachments   BOOLEAN DEFAULT FALSE,
    attachment_names  TEXT[],
    matched_keywords  TEXT[],
    snippet           TEXT,
    hash_sha256       VARCHAR(64),
    storage_path      TEXT,
    hold_status       VARCHAR(20) DEFAULT 'none',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_er_search_id   ON ediscovery_results (search_id);
CREATE INDEX IF NOT EXISTS idx_er_mailbox     ON ediscovery_results (mailbox);
CREATE INDEX IF NOT EXISTS idx_er_message_id  ON ediscovery_results (message_id);
CREATE INDEX IF NOT EXISTS idx_er_hold_status ON ediscovery_results (hold_status);

-- ============================================================================
-- 6. ediscovery_exports
-- ============================================================================
CREATE TABLE IF NOT EXISTS ediscovery_exports (
    id                BIGSERIAL PRIMARY KEY,
    case_id           BIGINT NOT NULL REFERENCES compliance_cases(id),
    search_id         BIGINT REFERENCES ediscovery_searches(id),
    export_format     VARCHAR(10) NOT NULL DEFAULT 'eml',
    result_ids        BIGINT[],
    total_messages    INTEGER DEFAULT 0,
    file_path         TEXT,
    file_hash_sha256  VARCHAR(64),
    file_size         BIGINT,
    gpg_signature     TEXT,
    timestamp_token   TEXT,
    exported_by       VARCHAR(255) NOT NULL,
    reason            TEXT NOT NULL,
    authorized_by     TEXT,
    exported_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ee_case_id ON ediscovery_exports (case_id);

-- Safe addition of new columns if table already existed without them
DO $$ BEGIN
    ALTER TABLE ediscovery_exports ADD COLUMN IF NOT EXISTS gpg_signature   TEXT;
    ALTER TABLE ediscovery_exports ADD COLUMN IF NOT EXISTS timestamp_token TEXT;
END $$;

-- ============================================================================
-- 7. legal_holds
-- ============================================================================
CREATE TABLE IF NOT EXISTS legal_holds (
    id              BIGSERIAL PRIMARY KEY,
    case_id         BIGINT REFERENCES compliance_cases(id),
    mailbox         VARCHAR(255) NOT NULL,
    scope           VARCHAR(50) DEFAULT 'all',
    folder_pattern  VARCHAR(255),
    date_from       TIMESTAMPTZ,
    date_to         TIMESTAMPTZ,
    reason          TEXT NOT NULL,
    enabled_by      VARCHAR(255) NOT NULL,
    disabled_by     VARCHAR(255),
    disable_reason  TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    enabled_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    disabled_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_lh_mailbox   ON legal_holds (mailbox);
CREATE INDEX IF NOT EXISTS idx_lh_is_active ON legal_holds (is_active);
CREATE INDEX IF NOT EXISTS idx_lh_case_id   ON legal_holds (case_id);

-- Safe addition of new column if table already existed without it
DO $$ BEGIN
    ALTER TABLE legal_holds ADD COLUMN IF NOT EXISTS disable_reason TEXT;
END $$;

-- ============================================================================
-- 8. fraud_alerts (NEW TABLE)
-- ============================================================================
CREATE TABLE IF NOT EXISTS fraud_alerts (
    id                  BIGSERIAL PRIMARY KEY,
    alert_type          VARCHAR(50) NOT NULL,
    severity            VARCHAR(20) NOT NULL DEFAULT 'medium',
    status              VARCHAR(20) NOT NULL DEFAULT 'open',
    username            VARCHAR(255),
    related_message_id  VARCHAR(500),
    related_case_id     BIGINT REFERENCES compliance_cases(id),
    description         TEXT,
    details             JSONB DEFAULT '{}',
    source_ip           INET,
    is_acknowledged     BOOLEAN DEFAULT FALSE,
    acknowledged_by     VARCHAR(255),
    acknowledged_at     TIMESTAMPTZ,
    closed_by           VARCHAR(255),
    closed_at           TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fa_alert_type       ON fraud_alerts (alert_type);
CREATE INDEX IF NOT EXISTS idx_fa_severity         ON fraud_alerts (severity);
CREATE INDEX IF NOT EXISTS idx_fa_status           ON fraud_alerts (status);
CREATE INDEX IF NOT EXISTS idx_fa_username         ON fraud_alerts (username);
CREATE INDEX IF NOT EXISTS idx_fa_created_at       ON fraud_alerts (created_at);
CREATE INDEX IF NOT EXISTS idx_fa_related_case_id  ON fraud_alerts (related_case_id);
CREATE INDEX IF NOT EXISTS idx_fa_is_acknowledged  ON fraud_alerts (is_acknowledged);

-- Safe addition of columns if fraud_alerts existed with a partial schema
DO $$ BEGIN
    ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS status             VARCHAR(20) NOT NULL DEFAULT 'open';
    ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS related_message_id VARCHAR(500);
    ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS related_case_id    BIGINT;
    ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS source_ip          INET;
    ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS closed_by          VARCHAR(255);
    ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS closed_at          TIMESTAMPTZ;
END $$;

-- Add FK constraint on related_case_id if it doesn't exist yet
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fraud_alerts_related_case_id_fkey'
          AND table_name = 'fraud_alerts'
    ) THEN
        BEGIN
            ALTER TABLE fraud_alerts
                ADD CONSTRAINT fraud_alerts_related_case_id_fkey
                FOREIGN KEY (related_case_id) REFERENCES compliance_cases(id);
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- Migration complete. All 8 tables created/verified:
--   1. user_activity_log
--   2. mail_trace
--   3. compliance_cases
--   4. ediscovery_searches
--   5. ediscovery_results
--   6. ediscovery_exports
--   7. legal_holds
--   8. fraud_alerts
-- ============================================================================
