-- Teléfonos institucionales (22/09/2026): anclas de red por sede (etapa 1 de la triangulación propia).
-- Una ancla es una red (subred interna o bloque público de una sede) o, en la etapa 2, un punto de
-- acceso wifi (BSSID) con coordenadas fijas. Si la IP con la que reporta el teléfono cae en una red
-- ancla, el servidor sabe que está en esa sede sin GPS y lo cruza con las demás posiciones.
-- Regla de privacidad: la posición por ancla solo se guarda en disp_ubicaciones si la ubicación del
-- equipo está autorizada o el equipo está perdido (igual que el GPS); «conectado a la red de X» sí se
-- muestra siempre en la telemetría, como ya se muestra la IP.
CREATE TABLE IF NOT EXISTS disp_anclas_red (
    id         SERIAL PRIMARY KEY,
    tipo       VARCHAR(8)   NOT NULL DEFAULT 'red' CHECK (tipo IN ('red', 'bssid')),
    valor      VARCHAR(64)  NOT NULL,      -- CIDR (193.16.0.0/24) o BSSID (aa:bb:cc:dd:ee:ff)
    sede       VARCHAR(120) NOT NULL,
    nombre     VARCHAR(160) NOT NULL DEFAULT '',
    lat        DOUBLE PRECISION NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon        DOUBLE PRECISION NOT NULL CHECK (lon BETWEEN -180 AND 180),
    radio_m    INT NOT NULL DEFAULT 60 CHECK (radio_m BETWEEN 5 AND 5000),
    activa     BOOLEAN NOT NULL DEFAULT TRUE,
    creado_por VARCHAR(255) NOT NULL DEFAULT 'sistema',
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tipo, valor)
);

-- Maquita central (Quito): coordenadas del GPS del servidor NTP stratum 1 (03-INFRAESTRUCTURA/stratum1_gps_ntp.md).
INSERT INTO disp_anclas_red (tipo, valor, sede, nombre, lat, lon, radio_m) VALUES
  ('red', '193.16.0.0/24',     'Maquita central', 'Red interna de la oficina (wifi y cable)', -0.2772, -78.5464, 60),
  ('red', '179.49.24.160/28',  'Maquita central', 'Bloque público de Maquita (salida a internet de la oficina)', -0.2772, -78.5464, 80)
ON CONFLICT (tipo, valor) DO NOTHING;

-- Último ancla reconocida por equipo (se muestra en la flota: «wifi · Maquita central»).
ALTER TABLE disp_equipos
    ADD COLUMN IF NOT EXISTS ancla_sede VARCHAR(120),
    ADD COLUMN IF NOT EXISTS ancla_en   TIMESTAMPTZ;

-- Nuevo origen de posición: 'ancla'.
ALTER TABLE disp_ubicaciones DROP CONSTRAINT IF EXISTS disp_ubicaciones_origen_check;
ALTER TABLE disp_ubicaciones ADD CONSTRAINT disp_ubicaciones_origen_check
    CHECK (origen IN ('periodica', 'comando', 'perdido', 'avistamiento', 'ancla'));
