-- Portal de dominio, quinta entrega (v1.11): fichas de API para usar el portal desde programas propios.
-- Cada ficha es de un administrador de dominio, con alcance (lectura y áreas donde puede cambiar) y caducidad.
-- Solo se guarda el hash (SHA-256) de la ficha y sus primeros caracteres. Se puede aplicar varias veces.
CREATE TABLE IF NOT EXISTS pd_fichas_api (
    id SERIAL PRIMARY KEY,
    admin_id INT NOT NULL REFERENCES pd_admins(id) ON DELETE CASCADE,
    nombre VARCHAR(80) NOT NULL,
    prefijo VARCHAR(16) NOT NULL,
    token_hash CHAR(64) NOT NULL UNIQUE,
    alcances TEXT[] NOT NULL CHECK (cardinality(alcances) BETWEEN 1 AND 7),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    last_ip VARCHAR(45),
    CHECK (expires_at <= created_at + INTERVAL '366 days')
);
CREATE INDEX IF NOT EXISTS pd_fichas_api_admin ON pd_fichas_api (admin_id);
