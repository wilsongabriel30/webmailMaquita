-- Preferencia «confirmación de lectura» (preguntar / siempre / nunca). El código la usa desde el 09/11/2026,
-- pero la columna solo estaba escrita en la documentación: en toda instalación que no fuera la de origen,
-- guardar cualquier ajuste (firma, respuesta automática) daba 500 (informe de Andes, 15/11/2026). Idempotente.
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS acuse_lectura varchar(12) NOT NULL DEFAULT 'preguntar';
