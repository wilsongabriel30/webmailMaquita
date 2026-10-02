-- Permisos que añade la multicuenta (asignar cuentas a personas desde el portal).
-- Sigue sin poder: leer contraseñas (ni de buzones ni de administradores), borrar buzones ni
-- crear administradores. De `admin` solo ve quién es administrador general, para no dejar
-- asignar esas cuentas.
GRANT SELECT, INSERT, DELETE ON mail_delegation TO panel_dominio;
GRANT UPDATE (can_send_as) ON mail_delegation TO panel_dominio;
GRANT USAGE ON SEQUENCE mail_delegation_id_seq TO panel_dominio;
GRANT SELECT (username, superadmin) ON admin TO panel_dominio;
