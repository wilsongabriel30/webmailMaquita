-- Cuentas «solo webmail» (12/11/2026): en estas cuentas la contraseña principal no sirve por
-- IMAP, POP3 ni SMTP desde fuera del propio servidor; siguen el webmail y las contraseñas de
-- aplicación. La consulta del passdb de Dovecot lee esta tabla (deploy/ajustes/81).
CREATE TABLE IF NOT EXISTS auth_cuentas_solo_web (
    username varchar(255) PRIMARY KEY,
    motivo   varchar(200) NOT NULL DEFAULT '',
    creada   timestamptz  NOT NULL DEFAULT now()
);
ALTER TABLE auth_cuentas_solo_web ADD COLUMN IF NOT EXISTS por varchar(255) NOT NULL DEFAULT '';
