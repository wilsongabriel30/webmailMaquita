-- Teléfonos institucionales (22/09/2026): varios IMEI por equipo (doble SIM, eSIM: 2 a 4). Los manda la
-- app cuando puede leerlos (solo con control completo desde Android 10) o los registra la persona desde
-- el correo web (*#06#) o Tecnología desde el panel. Se muestran a ambos para darlos a la operadora si
-- roban o pierden el teléfono. `imei` sigue siendo el principal (compatibilidad).
ALTER TABLE disp_equipos ADD COLUMN IF NOT EXISTS imeis JSONB NOT NULL DEFAULT '[]'::jsonb;
UPDATE disp_equipos SET imeis = jsonb_build_array(imei) WHERE imei IS NOT NULL AND imeis = '[]'::jsonb;
