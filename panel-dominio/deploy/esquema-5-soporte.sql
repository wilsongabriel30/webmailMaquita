-- Portal de dominio, quinta entrega: entrada de soporte «como el cliente» (2026-10-21).
-- El superadministrador (panel general o consola: maquita-panel-dominio vale-soporte) emite un vale
-- de un solo uso para UN dominio; el portal lo canjea por una sesión de soporte corta, sin la clave
-- ni el segundo factor del cliente. Se puede aplicar varias veces. La aplica el dueño de la base.

CREATE TABLE IF NOT EXISTS pd_vales_soporte (
    id SERIAL PRIMARY KEY,
    vale_hash VARCHAR(64) UNIQUE NOT NULL,          -- sha256 del vale: el vale en claro no se guarda
    domain VARCHAR(255) NOT NULL REFERENCES domain(domain) ON UPDATE CASCADE ON DELETE CASCADE,
    solo_lectura BOOLEAN NOT NULL DEFAULT true,
    superadmin VARCHAR(255) NOT NULL,               -- quién lo pidió (usuario del panel, o consola:<usuario>)
    origen VARCHAR(20) NOT NULL DEFAULT 'panel' CHECK (origen IN ('panel', 'consola')),
    motivo VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    usado_en TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS pd_sesiones_soporte (
    id SERIAL PRIMARY KEY,
    vale_id INT REFERENCES pd_vales_soporte(id) ON DELETE SET NULL,
    token_hash VARCHAR(64) NOT NULL,
    domain VARCHAR(255) NOT NULL REFERENCES domain(domain) ON UPDATE CASCADE ON DELETE CASCADE,
    superadmin VARCHAR(255) NOT NULL,
    solo_lectura BOOLEAN NOT NULL,
    ip VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_pd_sesiones_soporte_token ON pd_sesiones_soporte(token_hash);
