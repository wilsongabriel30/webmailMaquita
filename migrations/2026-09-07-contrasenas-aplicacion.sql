-- D-5: contraseñas de aplicación (una por cliente, revocables) para IMAP/SMTP/ActiveSync.
-- La contraseña principal deja de valer fuera del webmail cuando la política está activa.
--
-- Requiere pgcrypto (crypt/gen_salt con bcrypt); la crea el instalador como superusuario:
--   sudo -u postgres psql -d maildb -c "CREATE EXTENSION IF NOT EXISTS pgcrypto"
-- (esta línea falla sin permisos y el instalador la ignora; el resto no depende de ella para crearse).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS contrasenas_aplicacion (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    nombre VARCHAR(80) NOT NULL,
    hash TEXT NOT NULL,                 -- bcrypt (pgcrypto, bf), comparado en verificar_contrasena_aplicacion()
    prefijo CHAR(4) NOT NULL,           -- primeros 4 caracteres, para que la persona la reconozca
    creada TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultimo_uso TIMESTAMPTZ,
    ultimo_ip VARCHAR(64),
    revocada TIMESTAMPTZ,
    motivo_revocacion VARCHAR(80)
);
CREATE INDEX IF NOT EXISTS contrasenas_aplicacion_activas ON contrasenas_aplicacion (username) WHERE revocada IS NULL;

-- Política de autenticación leída por Dovecot en cada login (una fila por clave).
CREATE TABLE IF NOT EXISTS auth_politica (
    clave VARCHAR(64) PRIMARY KEY,
    valor TEXT NOT NULL,
    modificada TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- 'false' al instalar: primero se crean las contraseñas de aplicación, después se exige.
INSERT INTO auth_politica (clave, valor) VALUES ('contrasenas_aplicacion_obligatorias', 'false')
    ON CONFLICT (clave) DO NOTHING;

-- Verificación para Dovecot: devuelve la fila cuya contraseña coincide (bcrypt) y anota el uso.
-- Solo para clientes externos: desde el propio servidor (webmail) no vale; ahí se usa la principal.
-- Devuelve `nopassword` porque la comparación ya se hizo aquí sobre la clave sin guiones ni espacios;
-- si Dovecot volviera a comparar el hash, una clave tecleada con guiones fallaría.
CREATE OR REPLACE FUNCTION verificar_contrasena_aplicacion(p_user TEXT, p_clave TEXT, p_ip TEXT)
RETURNS TABLE ("user" TEXT, password TEXT, nopassword TEXT) AS $$
DECLARE
    fila contrasenas_aplicacion%ROWTYPE;
    limpia TEXT := regexp_replace(coalesce(p_clave, ''), '[-\s]', '', 'g');
BEGIN
    IF length(limpia) < 16 OR coalesce(p_ip, '') IN ('127.0.0.1', '::1') THEN
        RETURN;
    END IF;
    SELECT c.* INTO fila
      FROM contrasenas_aplicacion c
      JOIN mailbox m ON m.username = c.username
     WHERE c.username = p_user AND c.revocada IS NULL AND m.active = true
       AND c.hash = crypt(limpia, c.hash)
     LIMIT 1;
    IF NOT FOUND THEN
        RETURN;
    END IF;
    UPDATE contrasenas_aplicacion SET ultimo_uso = NOW(), ultimo_ip = left(coalesce(p_ip, ''), 64) WHERE id = fila.id;
    RETURN QUERY SELECT fila.username::TEXT, NULL::TEXT, 'y'::TEXT;
END
$$ LANGUAGE plpgsql;
