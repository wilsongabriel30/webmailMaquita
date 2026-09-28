-- Permisos que añade la segunda entrega. Sigue sin poder: leer contraseñas de buzones, borrar
-- buzones, leer configuración ni auditoría, crear administradores ni asignarse dominios.
GRANT UPDATE (totp_secret, totp_enabled, totp_last_step) ON pd_admins TO panel_dominio;

GRANT SELECT, INSERT ON pd_solicitudes TO panel_dominio;
GRANT USAGE ON SEQUENCE pd_solicitudes_id_seq TO panel_dominio;

-- Marca de cada empresa. Los nombres de servidor (portal_empresa) solo se leen: publicar uno
-- exige DNS, certificado y nginx, que son del administrador general.
GRANT SELECT, INSERT, UPDATE, DELETE ON branding_empresa TO panel_dominio;
GRANT SELECT ON portal_empresa TO panel_dominio;

-- Grupos de distribución.
GRANT SELECT, INSERT, UPDATE, DELETE ON mail_groups, mail_group_members TO panel_dominio;
GRANT USAGE ON SEQUENCE mail_groups_id_seq, mail_group_members_id_seq TO panel_dominio;
