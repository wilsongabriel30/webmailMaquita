-- Importar cuentas desde CSV (v1.11): el portal solo necesita SABER si un dominio suyo entrega su
-- correo en otro servidor (enrutamiento), para no crear cuentas que nunca recibirían nada. Solo
-- lectura y solo esas dos columnas: el destino del reenvío no le incumbe.
-- La misma concesión la hace la migración 2026-10-21-enrutamiento-correo.sql en una actualización;
-- aquí se repite porque permisos.sql empieza revocándolo todo.
DO $$
BEGIN
    IF to_regclass('public.enrutamiento_correo') IS NOT NULL THEN
        GRANT SELECT (dominio, activo) ON enrutamiento_correo TO panel_dominio;
    END IF;
END
$$;
