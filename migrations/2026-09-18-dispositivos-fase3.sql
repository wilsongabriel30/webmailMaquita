-- Teléfonos institucionales, fase 3: respaldos incrementales cifrados y restauración autorizada.
-- Los archivos se guardan por contenido (SHA-256) y por equipo; una instantánea es la lista
-- ruta -> contenido de un momento dado. Ver docs/DISPOSITIVOS.md.

ALTER TABLE disp_equipos
    ADD COLUMN IF NOT EXISTS respaldo_activo    BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS cuota_respaldo_gb  INT NOT NULL DEFAULT 64 CHECK (cuota_respaldo_gb BETWEEN 1 AND 2048),
    ADD COLUMN IF NOT EXISTS respaldo_cierre_en TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS disp_respaldos (
    id             SERIAL PRIMARY KEY,
    equipo_id      INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    tipo           VARCHAR(12) NOT NULL DEFAULT 'programado' CHECK (tipo IN ('programado', 'manual', 'cierre')),
    estado         VARCHAR(12) NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto', 'completo', 'incompleto')),
    iniciado_en    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cerrado_en     TIMESTAMPTZ,
    archivos_total INT NOT NULL DEFAULT 0,
    bytes_total    BIGINT NOT NULL DEFAULT 0,
    archivos_nuevos INT NOT NULL DEFAULT 0,
    bytes_nuevos   BIGINT NOT NULL DEFAULT 0,
    faltantes      INT NOT NULL DEFAULT 0,
    resumen        JSONB NOT NULL DEFAULT '{}'::jsonb,   -- por categoría: {fotos: {archivos, bytes}, whatsapp: {...}}
    errores        JSONB NOT NULL DEFAULT '[]'::jsonb,
    version_app    VARCHAR(40)
);
CREATE INDEX IF NOT EXISTS disp_respaldos_equipo ON disp_respaldos (equipo_id, iniciado_en DESC);

CREATE TABLE IF NOT EXISTS disp_respaldo_archivos (
    respaldo_id INT NOT NULL REFERENCES disp_respaldos(id) ON DELETE CASCADE,
    ruta        TEXT NOT NULL,
    categoria   VARCHAR(20) NOT NULL DEFAULT 'otros',
    sha256      CHAR(64) NOT NULL,
    tamano      BIGINT NOT NULL CHECK (tamano >= 0),
    mtime       TIMESTAMPTZ,
    PRIMARY KEY (respaldo_id, ruta)
);
CREATE INDEX IF NOT EXISTS disp_respaldo_archivos_sha ON disp_respaldo_archivos (sha256);

CREATE TABLE IF NOT EXISTS disp_objetos (
    equipo_id     INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    sha256        CHAR(64) NOT NULL,
    tamano        BIGINT NOT NULL,
    recibido      BIGINT NOT NULL DEFAULT 0,
    estado        VARCHAR(10) NOT NULL DEFAULT 'parcial' CHECK (estado IN ('parcial', 'completo')),
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completado_en TIMESTAMPTZ,
    PRIMARY KEY (equipo_id, sha256)
);

CREATE TABLE IF NOT EXISTS disp_restauraciones (
    id             SERIAL PRIMARY KEY,
    destino_id     INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    origen_id      INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    autorizado_por VARCHAR(255) NOT NULL,
    motivo         VARCHAR(255) NOT NULL,
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    caduca_en      TIMESTAMPTZ NOT NULL,
    anulada_en     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS disp_restauraciones_destino ON disp_restauraciones (destino_id);

UPDATE disp_config SET valor = valor || '{"version": 3, "respaldo": {"hora": "02:30", "solo_wifi": true, "solo_cargando": true, "categorias": ["fotos", "videos", "documentos", "descargas", "contactos", "llamadas", "sms", "whatsapp", "apps"], "instantaneas": 7}}'::jsonb,
       actualizado_en = NOW()
 WHERE clave = 'politica' AND NOT (valor ? 'respaldo');
