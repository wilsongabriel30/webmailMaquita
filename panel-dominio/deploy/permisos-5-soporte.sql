-- Permisos que añade la entrada de soporte. El portal (y el intermediario de los sitios, que entra
-- con su mismo usuario) solo CANJEA vales: los lee y los marca usados, pero no puede crearlos. Los
-- crea el panel general o la consola, con el usuario dueño de la base.
GRANT SELECT ON pd_vales_soporte TO panel_dominio;
GRANT UPDATE (usado_en) ON pd_vales_soporte TO panel_dominio;
GRANT SELECT, INSERT ON pd_sesiones_soporte TO panel_dominio;
GRANT UPDATE (revoked_at) ON pd_sesiones_soporte TO panel_dominio;
GRANT USAGE ON SEQUENCE pd_sesiones_soporte_id_seq TO panel_dominio;

-- El panel general entra con «mailserver». Si las tablas las creó otro dueño (p. ej. postgres desde
-- el ajuste 66), necesita el permiso expreso para emitir vales y ver las sesiones.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mailserver') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON pd_vales_soporte, pd_sesiones_soporte TO mailserver;
        GRANT USAGE ON SEQUENCE pd_vales_soporte_id_seq, pd_sesiones_soporte_id_seq TO mailserver;
    END IF;
END
$$;
