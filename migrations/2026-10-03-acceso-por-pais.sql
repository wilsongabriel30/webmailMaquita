-- Acceso al webmail por país: la tabla que leen el panel y geoip-rebuild.sh.
-- Existía solo en la instalación de origen (creada a mano). Idempotente.
CREATE TABLE IF NOT EXISTS geo_webmail_countries (
    code       varchar(2)   PRIMARY KEY,
    name       varchar(80)  NOT NULL,
    enabled    boolean      NOT NULL DEFAULT false,
    updated_by varchar(255),
    updated_at timestamptz  NOT NULL DEFAULT now()
);
