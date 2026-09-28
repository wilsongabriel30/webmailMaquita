-- Portal de administradores de dominio: tablas propias (prefijo pd_).
-- Las crea el dueño de la base del correo; el portal entra con el usuario panel_dominio,
-- que solo recibe los permisos de permisos.sql.

CREATE TABLE IF NOT EXISTS pd_admins (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL DEFAULT '',
    active BOOLEAN NOT NULL DEFAULT true,
    must_change_password BOOLEAN NOT NULL DEFAULT true,
    failed_attempts INT NOT NULL DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    last_login TIMESTAMP WITH TIME ZONE,
    created_by VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pd_admin_dominios (
    admin_id INT NOT NULL REFERENCES pd_admins(id) ON DELETE CASCADE,
    domain VARCHAR(255) NOT NULL REFERENCES domain(domain) ON UPDATE CASCADE ON DELETE CASCADE,
    assigned_by VARCHAR(255) NOT NULL DEFAULT '',
    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (admin_id, domain)
);

CREATE TABLE IF NOT EXISTS pd_sesiones (
    id SERIAL PRIMARY KEY,
    admin_id INT NOT NULL REFERENCES pd_admins(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL,
    ip VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_pd_sesiones_token ON pd_sesiones(token_hash);

CREATE TABLE IF NOT EXISTS pd_auditoria (
    id SERIAL PRIMARY KEY,
    admin_id INT,
    admin_username VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    target VARCHAR(255),
    details JSONB,
    ip VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pd_auditoria_fecha ON pd_auditoria(created_at DESC);
