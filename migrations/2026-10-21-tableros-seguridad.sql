-- Tableros de seguridad del panel general (Seguridad → Tableros), v1.11.
-- El recolector (maquita-seguridad-recolector.timer, cada 5 minutos) lee los registros de Postfix,
-- Dovecot y ActiveSync, la auditoría del webmail y del panel y las estadísticas de Rspamd, y deja aquí
-- los totales por hora: así el panel no recorre registros enormes en cada visita.
-- Idempotente. Se aplica como el usuario de la aplicación (el de DATABASE_URL).

-- Flujo de correo por hora (UTC, truncada a la hora).
CREATE TABLE IF NOT EXISTS seg_flujo_hora (
    hora              timestamptz PRIMARY KEY,
    recibidos         integer     NOT NULL DEFAULT 0,  -- entregados en buzones de este servidor
    enviados          integer     NOT NULL DEFAULT 0,  -- entregados a otros servidores
    rebotados         integer     NOT NULL DEFAULT 0,
    diferidos         integer     NOT NULL DEFAULT 0,  -- intentos aplazados (un mensaje puede sumar varios)
    rechazados        integer     NOT NULL DEFAULT 0,  -- rechazados en la conexión (NOQUEUE: reject)
    rechazados_filtro integer     NOT NULL DEFAULT 0,  -- rechazados por el filtro (milter-reject)
    analizados        integer     NOT NULL DEFAULT 0,  -- mensajes analizados por Rspamd
    spam_rechazado    integer     NOT NULL DEFAULT 0,  -- Rspamd: reject
    spam_marcado      integer     NOT NULL DEFAULT 0,  -- Rspamd: add header / rewrite subject
    spam_aplazado     integer     NOT NULL DEFAULT 0,  -- Rspamd: greylist / soft reject
    en_cola           integer                          -- último tamaño de la cola visto en esa hora
);

-- Inicios de sesión por hora, servicio, cuenta e IP (detalle: para los «top» y las reglas de anomalía).
-- Se conserva menos tiempo que los resúmenes (retencion_detalle_dias).
CREATE TABLE IF NOT EXISTS seg_accesos_detalle (
    hora     timestamptz  NOT NULL,
    servicio varchar(16)  NOT NULL,   -- webmail | imap | pop3 | smtp | activesync | panel
    cuenta   varchar(255) NOT NULL DEFAULT '',
    ip       varchar(64)  NOT NULL DEFAULT '',
    pais     varchar(8)   NOT NULL DEFAULT '',  -- ISO-2, «LAN» (red interna) o «--» (desconocido)
    ok       integer      NOT NULL DEFAULT 0,
    fallos   integer      NOT NULL DEFAULT 0,
    PRIMARY KEY (hora, servicio, cuenta, ip)
);
CREATE INDEX IF NOT EXISTS idx_seg_accesos_detalle_ip ON seg_accesos_detalle (ip, hora DESC);
CREATE INDEX IF NOT EXISTS idx_seg_accesos_detalle_cuenta ON seg_accesos_detalle (cuenta, hora DESC);

-- Resumen por hora, servicio y país (se recalcula desde el detalle para las horas tocadas).
CREATE TABLE IF NOT EXISTS seg_accesos_hora (
    hora     timestamptz NOT NULL,
    servicio varchar(16) NOT NULL,
    pais     varchar(8)  NOT NULL DEFAULT '',
    ok       integer     NOT NULL DEFAULT 0,
    fallos   integer     NOT NULL DEFAULT 0,
    cuentas  integer     NOT NULL DEFAULT 0,   -- cuentas distintas con algún acceso correcto
    ips      integer     NOT NULL DEFAULT 0,   -- IP distintas
    PRIMARY KEY (hora, servicio, pais)
);

-- Lo que el recolector aprende de cada cuenta para las reglas «país nuevo» y «hora inusual».
CREATE TABLE IF NOT EXISTS seg_cuenta_pais (
    cuenta      varchar(255) NOT NULL,
    pais        varchar(8)   NOT NULL,
    primera_vez timestamptz  NOT NULL DEFAULT now(),
    ultima_vez  timestamptz  NOT NULL DEFAULT now(),
    accesos     integer      NOT NULL DEFAULT 0,
    PRIMARY KEY (cuenta, pais)
);
CREATE TABLE IF NOT EXISTS seg_cuenta_hora (
    cuenta  varchar(255) NOT NULL,
    hora    smallint     NOT NULL CHECK (hora BETWEEN 0 AND 23),  -- hora local
    accesos integer      NOT NULL DEFAULT 0,
    PRIMARY KEY (cuenta, hora)
);

-- Alertas de anomalías: abierta → reconocida → cerrada (resuelta o falso positivo).
CREATE TABLE IF NOT EXISTS seg_alertas (
    id             bigserial    PRIMARY KEY,
    regla          varchar(32)  NOT NULL,   -- pais_nuevo | fallos_y_exito | hora_inusual | muchas_cuentas_ip
    severidad      varchar(8)   NOT NULL,   -- baja | media | alta
    cuenta         varchar(255) NOT NULL DEFAULT '',
    ip             varchar(64)  NOT NULL DEFAULT '',
    pais           varchar(8)   NOT NULL DEFAULT '',
    servicio       varchar(16)  NOT NULL DEFAULT '',
    descripcion    text         NOT NULL,
    detalles       jsonb        NOT NULL DEFAULT '{}'::jsonb,
    huella         varchar(200) NOT NULL,   -- evita repetir la misma alerta en cada pasada
    repeticiones   integer      NOT NULL DEFAULT 1,
    estado         varchar(12)  NOT NULL DEFAULT 'abierta',
    resolucion     varchar(16),             -- resuelta | falso_positivo
    nota           text,
    creada         timestamptz  NOT NULL DEFAULT now(),
    ultima_vez     timestamptz  NOT NULL DEFAULT now(),
    avisada        boolean      NOT NULL DEFAULT false,
    escalada_en    timestamptz,
    reconocida_por varchar(255),
    reconocida_en  timestamptz,
    cerrada_por    varchar(255),
    cerrada_en     timestamptz,
    CONSTRAINT seg_alertas_huella UNIQUE (huella),
    CONSTRAINT seg_alertas_estado CHECK (estado IN ('abierta', 'reconocida', 'cerrada')),
    CONSTRAINT seg_alertas_severidad CHECK (severidad IN ('baja', 'media', 'alta'))
);
CREATE INDEX IF NOT EXISTS idx_seg_alertas_estado ON seg_alertas (estado, creada DESC);
CREATE INDEX IF NOT EXISTS idx_seg_alertas_creada ON seg_alertas (creada DESC);

-- Configuración (una fila): retención, reglas y avisos.
CREATE TABLE IF NOT EXISTS seg_config (
    id                      integer     PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    retencion_dias          integer     NOT NULL DEFAULT 400,  -- resúmenes y alertas cerradas
    retencion_detalle_dias  integer     NOT NULL DEFAULT 90,   -- detalle por cuenta e IP
    zona_horaria            varchar(64) NOT NULL DEFAULT '',   -- vacío: la del servidor
    regla_pais_nuevo        boolean     NOT NULL DEFAULT true,
    regla_fallos_y_exito    boolean     NOT NULL DEFAULT true,
    regla_hora_inusual      boolean     NOT NULL DEFAULT true,
    regla_muchas_cuentas_ip boolean     NOT NULL DEFAULT true,
    umbral_fallos           integer     NOT NULL DEFAULT 5,
    ventana_fallos_min      integer     NOT NULL DEFAULT 15,
    umbral_cuentas_ip       integer     NOT NULL DEFAULT 10,
    hora_min_historial      integer     NOT NULL DEFAULT 50,
    hora_porcentaje_max     integer     NOT NULL DEFAULT 1,    -- % de los accesos de la cuenta a esa hora
    avisos                  boolean     NOT NULL DEFAULT true,
    aviso_severidad_minima  varchar(8)  NOT NULL DEFAULT 'alta',
    avisos_por_hora         integer     NOT NULL DEFAULT 6,
    escalar_tras_horas      integer     NOT NULL DEFAULT 4,    -- 0: sin escalamiento
    actualizado_por         varchar(255),
    actualizado_en          timestamptz DEFAULT now()
);
INSERT INTO seg_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- Estado del recolector (posición en cada registro, últimos id leídos, contadores de Rspamd…).
CREATE TABLE IF NOT EXISTS seg_estado (
    clave       varchar(64) PRIMARY KEY,
    valor       jsonb       NOT NULL DEFAULT '{}'::jsonb,
    actualizado timestamptz NOT NULL DEFAULT now()
);
