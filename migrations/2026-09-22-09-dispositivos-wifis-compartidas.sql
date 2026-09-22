-- Wifi compartido por los propios teléfonos (22/09/2026, dirección): eventos, hoteles, oficinas de
-- aliados. Cuando un compañero conecta su app a una red y acepta compartirla, el servidor la reparte a
-- toda la flota sin que Tecnología haga nada. `origen` distingue las que registró el panel.
ALTER TABLE disp_wifis
    ADD COLUMN IF NOT EXISTS origen         VARCHAR(12) NOT NULL DEFAULT 'panel' CHECK (origen IN ('panel', 'telefono')),
    ADD COLUMN IF NOT EXISTS compartida_por VARCHAR(255),
    ADD COLUMN IF NOT EXISTS equipo_id      INT REFERENCES disp_equipos(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS bssid          VARCHAR(17),
    ADD COLUMN IF NOT EXISTS ultimo_uso     TIMESTAMPTZ;
