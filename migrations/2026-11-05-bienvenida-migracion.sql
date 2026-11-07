-- Bienvenida tras una migración de correo (03/11/2026): primer ingreso de cada persona después del cambio.
-- Desde esa fecha cuentan los días en que ve la ventana (BIENVENIDA_DIAS). Idempotente.
CREATE TABLE IF NOT EXISTS bienvenida_migracion (
    username    TEXT PRIMARY KEY,
    primera_vez TIMESTAMPTZ NOT NULL DEFAULT now()
);
