-- Reacciones a un correo (una por persona y correo), ligadas al Message-ID. Idempotente.
CREATE TABLE IF NOT EXISTS mail_reacciones (
    message_id text        NOT NULL,
    usuario    text        NOT NULL,
    emoji      text        NOT NULL,
    creado     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (message_id, usuario)
);
