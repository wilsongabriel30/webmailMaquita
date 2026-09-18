-- Teléfonos institucionales: avisos push nativos (ntfy autoalojado, sin Google). Cada equipo tiene un
-- tema secreto en ntfy; el backend publica un aviso «sync» y el teléfono despierta y hace su latido.
ALTER TABLE disp_equipos ADD COLUMN IF NOT EXISTS push_topic CHAR(37);
UPDATE disp_config SET valor = valor || '{"push": {"servidor": "https://mail.maquita.org:2587"}}'::jsonb, actualizado_en = NOW()
 WHERE clave = 'politica' AND NOT (valor ? 'push');
