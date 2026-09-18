-- Gestión de teléfonos institucionales, fase 1: enrolamiento, inventario, latidos,
-- mensajes urgentes con acuse y eventos de seguridad. Propuesta y contrato:
-- docs/DISPOSITIVOS.md. El webmail atiende a los teléfonos; el panel administra.

CREATE TABLE IF NOT EXISTS disp_codigos (
    id          SERIAL PRIMARY KEY,
    codigo_hash CHAR(64) NOT NULL UNIQUE,
    prefijo     CHAR(4)  NOT NULL,
    etiqueta    VARCHAR(120) NOT NULL DEFAULT '',
    modo        VARCHAR(12)  NOT NULL DEFAULT 'propietario' CHECK (modo IN ('propietario', 'limitado')),
    usos_max    INT NOT NULL DEFAULT 1 CHECK (usos_max BETWEEN 1 AND 500),
    usos        INT NOT NULL DEFAULT 0,
    creado_por  VARCHAR(255) NOT NULL,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    caduca_en   TIMESTAMPTZ,
    revocado_en TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS disp_equipos (
    id                   SERIAL PRIMARY KEY,
    id_instalacion       VARCHAR(80) NOT NULL UNIQUE,
    token_hash           CHAR(64) NOT NULL UNIQUE,
    codigo_id            INT REFERENCES disp_codigos(id) ON DELETE SET NULL,
    modo                 VARCHAR(12) NOT NULL DEFAULT 'limitado',
    estado               VARCHAR(12) NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'revocado', 'perdido', 'baja')),
    -- inventario que reporta el teléfono
    fabricante           VARCHAR(80),
    modelo               VARCHAR(120),
    serie                VARCHAR(80),
    imei                 VARCHAR(20),
    android              VARCHAR(40),
    version_app          VARCHAR(40),
    -- lo que completa Tecnología
    nombre               VARCHAR(120) NOT NULL DEFAULT '',
    custodio_email       VARCHAR(255),
    custodio_nombre      VARCHAR(160),
    centro_costo         VARCHAR(120),
    sede                 VARCHAR(120),
    fecha_compra         DATE,
    valor_compra         NUMERIC(12,2),
    vida_util_meses      INT NOT NULL DEFAULT 36,
    factura_ref          VARCHAR(255),
    notas                TEXT,
    -- último estado conocido
    enrolado_en          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultimo_contacto      TIMESTAMPTZ,
    ultima_ip            VARCHAR(64),
    bateria              SMALLINT,
    cargando             BOOLEAN,
    almacenamiento_libre BIGINT,
    almacenamiento_total BIGINT,
    red                  VARCHAR(40),
    play_protect         BOOLEAN,
    revocado_en          TIMESTAMPTZ,
    revocado_motivo      VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS disp_equipos_custodio ON disp_equipos (custodio_email);

CREATE TABLE IF NOT EXISTS disp_latidos (
    id          BIGSERIAL PRIMARY KEY,
    equipo_id   INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    recibido_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip          VARCHAR(64),
    datos       JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS disp_latidos_equipo ON disp_latidos (equipo_id, recibido_en DESC);

CREATE TABLE IF NOT EXISTS disp_mensajes (
    id              SERIAL PRIMARY KEY,
    titulo          VARCHAR(160) NOT NULL,
    texto           TEXT NOT NULL,
    nivel           VARCHAR(12) NOT NULL DEFAULT 'urgente' CHECK (nivel IN ('informativo', 'importante', 'urgente')),
    requiere_acuse  BOOLEAN NOT NULL DEFAULT TRUE,
    destino         VARCHAR(12) NOT NULL DEFAULT 'todos' CHECK (destino IN ('todos', 'equipos')),
    creado_por      VARCHAR(255) NOT NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    caduca_en       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS disp_mensajes_equipos (
    mensaje_id   INT NOT NULL REFERENCES disp_mensajes(id) ON DELETE CASCADE,
    equipo_id    INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    entregado_en TIMESTAMPTZ,
    leido_en     TIMESTAMPTZ,
    PRIMARY KEY (mensaje_id, equipo_id)
);
CREATE INDEX IF NOT EXISTS disp_mensajes_equipos_pend ON disp_mensajes_equipos (equipo_id) WHERE leido_en IS NULL;

CREATE TABLE IF NOT EXISTS disp_comandos (
    id           SERIAL PRIMARY KEY,
    equipo_id    INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    tipo         VARCHAR(24) NOT NULL,
    parametros   JSONB NOT NULL DEFAULT '{}'::jsonb,
    estado       VARCHAR(12) NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'entregado', 'hecho', 'fallido', 'anulado')),
    creado_por   VARCHAR(255) NOT NULL,
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    entregado_en TIMESTAMPTZ,
    terminado_en TIMESTAMPTZ,
    resultado    JSONB
);
CREATE INDEX IF NOT EXISTS disp_comandos_pend ON disp_comandos (equipo_id) WHERE estado = 'pendiente';

CREATE TABLE IF NOT EXISTS disp_eventos (
    id          BIGSERIAL PRIMARY KEY,
    equipo_id   INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    tipo        VARCHAR(40) NOT NULL,
    detalle     JSONB NOT NULL DEFAULT '{}'::jsonb,
    recibido_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    visto_por   VARCHAR(255),
    visto_en    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS disp_eventos_equipo ON disp_eventos (equipo_id, recibido_en DESC);

CREATE TABLE IF NOT EXISTS disp_config (
    clave VARCHAR(60) PRIMARY KEY,
    valor JSONB NOT NULL,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO disp_config (clave, valor) VALUES
  ('politica', '{"version": 1, "latido_minutos": 15, "contacto_ti": "Tecnología Maquita", "telefono_ti": "", "aviso_privacidad": "Este equipo es propiedad de la Fundación y está administrado por Tecnología: se registran su estado, su inventario y los mensajes institucionales. No se leen mensajes, fotos ni contenido personal."}')
ON CONFLICT (clave) DO NOTHING;
