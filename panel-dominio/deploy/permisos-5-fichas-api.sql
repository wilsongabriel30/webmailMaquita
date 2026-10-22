-- Permisos de las fichas de API del portal (v1.11). El portal las crea, las lista, anota su último uso y las
-- revoca (nunca las borra: quedan para la auditoría). El intermediario de los sitios entra con el mismo usuario
-- y solo necesita leerlas.
GRANT SELECT, INSERT, UPDATE ON pd_fichas_api TO panel_dominio;
GRANT USAGE, SELECT ON SEQUENCE pd_fichas_api_id_seq TO panel_dominio;

-- El panel general (rol «mailserver») las ve y las puede revocar al desactivar o restablecer una cuenta.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mailserver') THEN
        GRANT SELECT, UPDATE ON pd_fichas_api TO mailserver;
    END IF;
END
$$;
