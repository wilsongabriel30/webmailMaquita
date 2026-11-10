-- Foto de perfil: «la foto de Raíces manda» (09/11/2026). Idempotente.
-- `photo_url` sigue siendo la foto EFECTIVA que leen todas las vistas (avatars, foto, directorio, búsqueda).
-- Las columnas nuevas separan la foto de Raíces (con su huella para detectar cambios) de la propia del correo.
-- Ejecutar como dueño de la tabla (el usuario de la aplicación no es dueño de user_profiles).
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS foto_raices_url    TEXT NOT NULL DEFAULT '';
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS foto_raices_huella TEXT NOT NULL DEFAULT '';
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS foto_propia_url    TEXT NOT NULL DEFAULT '';
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS foto_origen        TEXT NOT NULL DEFAULT '';

-- Compatibilidad con las filas anteriores:
--  * fuente='nomina' con foto de la intranet → esa foto es la de Raíces (huella = URL; el conector la
--    recalcula en la siguiente sincronización sin pisar nada, porque la URL no cambia).
UPDATE user_profiles
   SET foto_raices_url = photo_url, foto_raices_huella = 'url:' || photo_url, foto_origen = 'nomina'
 WHERE fuente = 'nomina' AND COALESCE(photo_url, '') LIKE 'http%' AND foto_raices_url = '';
--  * foto propia servida por el correo (/api/contacts/foto/<correo>) → foto propia vigente.
UPDATE user_profiles
   SET foto_propia_url = photo_url, foto_origen = 'propio'
 WHERE COALESCE(photo_url, '') LIKE '/api/contacts/foto/%' AND foto_propia_url = '';
