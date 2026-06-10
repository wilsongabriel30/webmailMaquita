-- Safe Attachments Fase 1: analisis estatico/heuristico de adjuntos. Arranca APAGADO/SIMULACION.
CREATE TABLE IF NOT EXISTS safeattach_config (
  id int PRIMARY KEY DEFAULT 1 CHECK (id=1),
  enabled boolean NOT NULL DEFAULT false,
  enforce boolean NOT NULL DEFAULT false,
  window_hours int NOT NULL DEFAULT 24,
  max_per_user int NOT NULL DEFAULT 200,
  quarantine_folder varchar(64) NOT NULL DEFAULT 'Junk',
  quarantine_suspicious boolean NOT NULL DEFAULT false,  -- false=solo 'malicious'; true=tambien 'suspicious'
  scan_archives boolean NOT NULL DEFAULT true,
  updated_at timestamptz DEFAULT now()
);
INSERT INTO safeattach_config (id) VALUES (1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS safeattach_results (
  id bigserial PRIMARY KEY,
  username varchar(255) NOT NULL, message_id text, subject text, sender text,
  filename text, sha256 varchar(64), verdict varchar(16), reasons text,
  mailbox_from varchar(64), uid varchar(64), guid text,
  status varchar(16) NOT NULL DEFAULT 'simulado', created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_safeattach_status ON safeattach_results(status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_safeattach_msg ON safeattach_results(username, message_id, sha256);
GRANT ALL ON safeattach_config, safeattach_results TO mailserver;
GRANT USAGE, SELECT ON SEQUENCE safeattach_results_id_seq TO mailserver;
