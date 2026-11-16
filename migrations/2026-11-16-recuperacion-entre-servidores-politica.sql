-- Recuperación entre servidores: política sobre los correos ya leídos, administrada desde el panel
-- (16/11/2026). Una sola fila. Mientras no exista, rigen las variables del .env
-- (RECALL_FEDERADO_RETIRAR_LEIDOS y RECALL_FEDERADO_DOMINIOS_CONFIANZA). Idempotente.
CREATE TABLE IF NOT EXISTS federacion_recuperacion_politica (
    id                 smallint     PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    retirar_leidos     boolean      NOT NULL DEFAULT false,
    dominios_confianza text[]       NOT NULL DEFAULT '{}',
    actualizado        timestamptz  NOT NULL DEFAULT now(),
    por                varchar(255) NOT NULL DEFAULT ''
);
