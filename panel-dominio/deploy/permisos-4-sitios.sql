-- Permisos que añade «Mi sitio web». El portal (y el intermediario, que entra con su mismo usuario)
-- solo LEE las cuotas: no puede subírselas. Las escribe el panel general, con su propio rol.
GRANT SELECT ON pd_cuotas_sitio TO panel_dominio;

-- El panel general entra con «mailserver» (deploy/webmail/instalar.sh). Si la tabla la creó otro
-- dueño (p. ej. postgres desde el ajuste 58), necesita el permiso expreso para escribirla.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mailserver') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON pd_cuotas_sitio TO mailserver;
    END IF;
END
$$;
