-- Portales por empresa (14/09/2026)
--
-- Cada empresa entra al correo por su propio nombre de servidor: quien escribe
-- mail.<empresa> ve la marca de esa empresa y solo puede entrar con una cuenta de ese
-- dominio. El portal padre no restringe: desde ahi entra cualquier cuenta de la casa.
--
-- Se puede aplicar varias veces sin efectos secundarios.

CREATE TABLE IF NOT EXISTS portal_empresa (
    host       text PRIMARY KEY,
    dominio    text NOT NULL REFERENCES domain(domain) ON UPDATE CASCADE,
    activo     boolean NOT NULL DEFAULT true,
    creado_en  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE portal_empresa IS
    'Nombre de servidor por el que entra cada empresa. El dominio padre no se lista aqui: '
    'lo que no esta en esta tabla no restringe el dominio de la cuenta.';

-- Marca (logo, nombre, colores) por dominio de empresa. Lo que no este definido aqui
-- se hereda de la marca general, en branding_settings.
CREATE TABLE IF NOT EXISTS branding_empresa (
    dominio  text NOT NULL REFERENCES domain(domain) ON UPDATE CASCADE,
    clave    text NOT NULL,
    valor    text,
    PRIMARY KEY (dominio, clave)
);

COMMENT ON TABLE branding_empresa IS
    'Marca propia de cada empresa para la pantalla de entrada. Las claves son las mismas '
    'que en branding_settings (org_name, org_slogan, primary_color, footer_text...).';

-- Los portales de cada empresa y su marca se dan de alta en cada instalacion; no
-- viajan en el repositorio. Ejemplo de alta:
--
--   INSERT INTO portal_empresa (host, dominio)
--        VALUES ('mail.<empresa>', '<dominio de la empresa>');
--   INSERT INTO branding_empresa (dominio, clave, valor)
--        VALUES ('<dominio de la empresa>', 'org_name', '<nombre visible>');
--
-- El servicio del correo lee estas tablas con un usuario propio, que necesita permiso:
--
--   GRANT SELECT ON portal_empresa, branding_empresa TO <usuario de la aplicacion>;
