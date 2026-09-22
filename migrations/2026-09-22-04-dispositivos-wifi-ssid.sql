-- Teléfonos institucionales (22/09/2026): nombre del wifi al que está conectado el teléfono, tal como
-- lo reporta la app (`wifi_ssid` del latido). Para la persona: «tu teléfono está conectado al wifi de
-- tu casa» dice más que un mapa. Etapa 2: `wifi_bssid` (MAC del punto de acceso) para las anclas.
ALTER TABLE disp_equipos
    ADD COLUMN IF NOT EXISTS wifi_ssid  VARCHAR(64),
    ADD COLUMN IF NOT EXISTS wifi_bssid VARCHAR(17),
    ADD COLUMN IF NOT EXISTS wifi_en    TIMESTAMPTZ;
