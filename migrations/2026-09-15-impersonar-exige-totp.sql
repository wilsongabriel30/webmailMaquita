-- Impersonar buzones: ¿exige que el administrador haya entrado con segundo factor? (15/09/2026)
--
-- Se administra desde el panel (Anti-suplantación y políticas). Por omisión, sí (A-17).
-- Panel y backend del correo leen esta misma columna. Se puede aplicar varias veces.

ALTER TABLE security_config
    ADD COLUMN IF NOT EXISTS impersonar_admin_exige_totp boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN security_config.impersonar_admin_exige_totp IS
    'true: impersonar un buzon exige sesion del panel abierta con TOTP. false: basta la contrasena del panel '
    '(decision de la direccion). La auditoria registra cada impersonacion en ambos casos.';
