-- Plazo para recuperar un correo enviado, administrado desde el panel (19/11/2026). Una sola fila.
-- minutos_leidos:   plazo cuando el destinatario ya lo leyó (0 = lo ya leído no se recupera).
-- minutos_sin_leer: plazo mientras siga sin leer (0 = sin límite).
-- Mientras no exista la fila rige RECALL_MAX_MINUTOS del .env para lo leído y «sin límite» para lo
-- no leído (backend/app/mail/services/plazo_recuperacion.py). Idempotente.
CREATE TABLE IF NOT EXISTS recuperacion_plazo_politica (
    id               smallint     PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    minutos_leidos   integer      NOT NULL DEFAULT 60 CHECK (minutos_leidos BETWEEN 0 AND 43200),
    minutos_sin_leer integer      NOT NULL DEFAULT 0 CHECK (minutos_sin_leer BETWEEN 0 AND 43200),
    actualizado      timestamptz  NOT NULL DEFAULT now(),
    por              varchar(255) NOT NULL DEFAULT ''
);
