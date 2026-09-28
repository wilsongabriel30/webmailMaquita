-- Las imágenes remotas se muestran solas para todos (28/09/2026).
-- El valor guardado hasta hoy era el predeterminado anterior, no una elección: se pone en falso.
-- Quien quiera bloquearlas lo activa en Configuración.
ALTER TABLE user_preferences ALTER COLUMN block_remote_images SET DEFAULT false;
UPDATE user_preferences SET block_remote_images = false WHERE block_remote_images IS DISTINCT FROM false;
