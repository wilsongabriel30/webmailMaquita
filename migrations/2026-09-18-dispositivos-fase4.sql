-- Teléfonos institucionales, fase 4: inventario de aplicaciones con aviso de apps de riesgo,
-- reasignación de equipos con historial de custodia y destino configurable del respaldo.

-- Destino del respaldo dentro del almacén y usuario del teléfono ya existen (custodio_*); se añade la
-- carpeta lógica del respaldo (para organizar por persona o centro de costo). Vacía = la numérica del id.
ALTER TABLE disp_equipos
    ADD COLUMN IF NOT EXISTS carpeta_respaldo VARCHAR(80);

-- Inventario de apps: la última foto que envió cada teléfono.
CREATE TABLE IF NOT EXISTS disp_apps (
    equipo_id     INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    paquete       VARCHAR(255) NOT NULL,
    nombre        VARCHAR(255),
    version       VARCHAR(80),
    instalador    VARCHAR(120),
    firma_sha256  CHAR(64),
    permisos      JSONB NOT NULL DEFAULT '[]'::jsonb,
    sistema       BOOLEAN NOT NULL DEFAULT FALSE,
    veredicto     VARCHAR(12) NOT NULL DEFAULT 'ok' CHECK (veredicto IN ('ok', 'sospechosa', 'bloqueada')),
    motivo        VARCHAR(255),
    primera_vez   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    vista_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (equipo_id, paquete)
);
CREATE INDEX IF NOT EXISTS disp_apps_veredicto ON disp_apps (veredicto) WHERE veredicto <> 'ok';

-- Reglas y lista de bloqueo de apps (las mantiene Tecnología).
CREATE TABLE IF NOT EXISTS disp_apps_reglas (
    id         SERIAL PRIMARY KEY,
    tipo       VARCHAR(16) NOT NULL CHECK (tipo IN ('paquete', 'firma', 'permiso', 'instalador')),
    valor      VARCHAR(255) NOT NULL,
    accion     VARCHAR(12) NOT NULL DEFAULT 'avisar' CHECK (accion IN ('avisar', 'bloquear', 'permitir')),
    nota       VARCHAR(255),
    creado_por VARCHAR(255) NOT NULL,
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tipo, valor)
);
-- Semillas: instaladores de confianza (permitir) y señales de riesgo comunes (avisar).
INSERT INTO disp_apps_reglas (tipo, valor, accion, nota, creado_por) VALUES
  ('instalador', 'com.android.vending', 'permitir', 'Google Play', 'sistema'),
  ('instalador', 'com.sec.android.app.samsungapps', 'permitir', 'Galaxy Store', 'sistema'),
  ('permiso', 'android.permission.BIND_ACCESSIBILITY_SERVICE', 'avisar', 'Servicio de accesibilidad: común en fraude bancario', 'sistema'),
  ('permiso', 'android.permission.BIND_DEVICE_ADMIN', 'avisar', 'Administrador del dispositivo ajeno', 'sistema'),
  ('permiso', 'android.permission.SYSTEM_ALERT_WINDOW', 'avisar', 'Dibujar sobre otras apps (superposición)', 'sistema')
ON CONFLICT (tipo, valor) DO NOTHING;

-- Historial de custodia: quién tuvo el equipo y en qué periodo (cadena jefe -> subordinado -> técnico).
CREATE TABLE IF NOT EXISTS disp_custodia (
    id             SERIAL PRIMARY KEY,
    equipo_id      INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    custodio_email VARCHAR(255),
    custodio_nombre VARCHAR(160),
    centro_costo   VARCHAR(120),
    sede           VARCHAR(120),
    desde          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hasta          TIMESTAMPTZ,
    asignado_por   VARCHAR(255) NOT NULL,
    motivo         VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS disp_custodia_equipo ON disp_custodia (equipo_id, desde DESC);

UPDATE disp_config SET valor = valor || '{"version": 4, "apps": {"exigir_play_protect": true, "reinventariar_horas": 24}}'::jsonb,
       actualizado_en = NOW()
 WHERE clave = 'politica' AND NOT (valor ? 'apps');
