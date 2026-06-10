-- ZAP (Zero-hour Auto Purge): retiro de correos ya entregados que resultan
-- maliciosos segun los feeds de amenazas. NO borra: mueve a cuarentena (Junk),
-- reversible desde el panel :8443. Arranca APAGADO y en SIMULACION.
CREATE TABLE IF NOT EXISTS zap_config (
  id int PRIMARY KEY DEFAULT 1 CHECK (id=1),
  enabled boolean NOT NULL DEFAULT false,
  enforce boolean NOT NULL DEFAULT false,
  window_hours int NOT NULL DEFAULT 48,
  include_phishing boolean NOT NULL DEFAULT false,
  max_per_user int NOT NULL DEFAULT 200,
  quarantine_folder varchar(64) NOT NULL DEFAULT 'Junk',
  updated_at timestamptz DEFAULT now()
);
INSERT INTO zap_config (id) VALUES (1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS zap_actions (
  id bigserial PRIMARY KEY,
  username varchar(255) NOT NULL, message_id text, subject text, sender text,
  bad_host text, feed varchar(32), mailbox_from varchar(64), uid varchar(64),
  guid text, status varchar(16) NOT NULL DEFAULT 'simulado', created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_zap_actions_status ON zap_actions(status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_zap_msg ON zap_actions(username, message_id, bad_host);
GRANT ALL ON zap_config, zap_actions TO mailserver;
GRANT USAGE, SELECT ON SEQUENCE zap_actions_id_seq TO mailserver;
