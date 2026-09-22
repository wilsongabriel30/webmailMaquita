-- Teléfonos institucionales (22/09/2026, pedido de dirección): wifi de las sedes compartido con toda la
-- flota. Tecnología registra el wifi de cada sede (clave cifrada con DISP_CODIGO_CLAVE, nunca en claro
-- en la base); los teléfonos enrolados reciben la lista y se conectan solos al llegar. Si una clave
-- cambia y un teléfono la corrige y logra conectarse, el servidor la replica al resto.
CREATE TABLE IF NOT EXISTS disp_wifis (
    id              SERIAL PRIMARY KEY,
    sede            VARCHAR(120) NOT NULL,
    ssid            VARCHAR(32)  NOT NULL,
    clave_cifrada   TEXT,                                   -- NULL = red abierta
    seguridad       VARCHAR(8)   NOT NULL DEFAULT 'WPA' CHECK (seguridad IN ('WPA', 'WPA3', 'NONE')),
    oculta          BOOLEAN NOT NULL DEFAULT FALSE,
    activa          BOOLEAN NOT NULL DEFAULT TRUE,
    nota            VARCHAR(160) NOT NULL DEFAULT '',
    version         INT NOT NULL DEFAULT 1,
    actualizado_por VARCHAR(255) NOT NULL,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (sede, ssid)
);
-- Versión global de la lista: sube con cada cambio; va en la respuesta del latido para que la app sepa
-- cuándo volver a pedirla. Historial de cambios para saber quién corrigió qué.
INSERT INTO disp_config (clave, valor) VALUES ('wifis', '{"version": 1}') ON CONFLICT (clave) DO NOTHING;
CREATE TABLE IF NOT EXISTS disp_wifis_cambios (
    id         SERIAL PRIMARY KEY,
    wifi_id    INT NOT NULL REFERENCES disp_wifis(id) ON DELETE CASCADE,
    origen     VARCHAR(12) NOT NULL CHECK (origen IN ('panel', 'telefono')),
    quien      VARCHAR(255) NOT NULL,        -- usuario del panel o «equipo <id>»
    equipo_id  INT REFERENCES disp_equipos(id) ON DELETE SET NULL,
    detalle    VARCHAR(160) NOT NULL DEFAULT '',
    hecho_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
