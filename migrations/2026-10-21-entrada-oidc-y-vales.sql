-- Panel general (8443): entrada por OpenID Connect y vales de entrada de un solo uso (2026-10-21).
-- Idempotente. Se aplica como el usuario de la aplicación (el de DATABASE_URL), como las demás.
-- Detalle: docs/ENTRADA-OIDC-Y-SOPORTE.md

-- Configuración del proveedor de identidad (una sola fila). El client_secret se guarda cifrado con
-- la llave de credenciales (CREDENTIAL_ENCRYPTION_KEY, Fernet): nunca en claro.
CREATE TABLE IF NOT EXISTS admin_oidc_config (
    id                    integer      PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    activado              boolean      NOT NULL DEFAULT false,
    emisor                varchar(500) NOT NULL DEFAULT '',   -- issuer
    client_id             varchar(255) NOT NULL DEFAULT '',
    client_secret_cifrado text         NOT NULL DEFAULT '',
    claim_usuario         varchar(64)  NOT NULL DEFAULT 'preferred_username',
    claim_grupos          varchar(64)  NOT NULL DEFAULT '',
    grupo_requerido       varchar(255) NOT NULL DEFAULT '',
    crear_si_no_existe    boolean      NOT NULL DEFAULT false,
    rol_nuevo             varchar(20)  NOT NULL DEFAULT 'viewer' CHECK (rol_nuevo IN ('superadmin', 'admin', 'viewer')),
    texto_boton           varchar(60)  NOT NULL DEFAULT 'Entrar con Identidad',
    actualizado_por       varchar(255) NOT NULL DEFAULT '',
    actualizado_en        timestamptz  NOT NULL DEFAULT now()
);
INSERT INTO admin_oidc_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- Peticiones de entrada en curso (state, nonce y verificador PKCE). Viven 10 minutos y se usan una vez.
CREATE TABLE IF NOT EXISTS admin_oidc_flujos (
    state_hash   varchar(64)  PRIMARY KEY,
    nonce        varchar(128) NOT NULL,
    verificador  varchar(128) NOT NULL,
    redirect_uri varchar(500) NOT NULL,
    ip           varchar(45),
    created_at   timestamptz  NOT NULL DEFAULT now(),
    expires_at   timestamptz  NOT NULL
);

-- Vales de entrada de un solo uso: los emite la consola (maquita-panel vale-entrada) o la vuelta del
-- proveedor de identidad. Solo se guarda su hash. «exige_totp»: el segundo factor se pide al canjearlo.
CREATE TABLE IF NOT EXISTS admin_vales_entrada (
    id          serial       PRIMARY KEY,
    vale_hash   varchar(64)  UNIQUE NOT NULL,
    user_id     integer      NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    origen      varchar(20)  NOT NULL CHECK (origen IN ('consola', 'oidc')),
    exige_totp  boolean      NOT NULL DEFAULT false,
    creado_por  varchar(255) NOT NULL DEFAULT '',
    created_at  timestamptz  NOT NULL DEFAULT now(),
    expires_at  timestamptz  NOT NULL,
    usado_en    timestamptz,
    usado_ip    varchar(45)
);
