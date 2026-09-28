-- Permisos mínimos del usuario de base de datos del portal (panel_dominio).
-- Todo lo que no está aquí le está negado: configuración, auditoría del panel general,
-- administradores, firmas, cumplimiento, dispositivos...
-- No puede BORRAR buzones, ni crear administradores, ni asignarse dominios, ni leer o
-- borrar su propia auditoría.

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM panel_dominio;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM panel_dominio;
GRANT USAGE ON SCHEMA public TO panel_dominio;

GRANT SELECT ON domain TO panel_dominio;
GRANT SELECT (username, name, domain, quota, active, phone, email_other, created, modified) ON mailbox TO panel_dominio;
GRANT INSERT (username, password, name, maildir, quota, domain, local_part, active, phone, email_other) ON mailbox TO panel_dominio;
GRANT UPDATE (password, name, quota, active, phone, email_other, modified) ON mailbox TO panel_dominio;
GRANT SELECT, INSERT, UPDATE, DELETE ON alias TO panel_dominio;
GRANT SELECT (address) ON mail_groups TO panel_dominio;

GRANT SELECT ON pd_admins, pd_admin_dominios TO panel_dominio;
GRANT UPDATE (password_hash, must_change_password, failed_attempts, locked_until, last_login) ON pd_admins TO panel_dominio;
GRANT SELECT, INSERT ON pd_sesiones TO panel_dominio;
GRANT UPDATE (revoked_at) ON pd_sesiones TO panel_dominio;
GRANT INSERT ON pd_auditoria TO panel_dominio;
GRANT USAGE ON SEQUENCE pd_sesiones_id_seq, pd_auditoria_id_seq TO panel_dominio;
