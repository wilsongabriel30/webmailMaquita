-- Portal de dominio, cuarta entrega: «Mi sitio web». Cuotas de sitios web por dominio asignado.
-- Las fija el superadministrador en el panel general; las aplica el intermediario
-- maquita-sitios-portal. Sin fila para un dominio valen las de por defecto (1 sitio, 2 GB de disco,
-- 1 GB de bases de datos). Se puede aplicar varias veces.
CREATE TABLE IF NOT EXISTS pd_cuotas_sitio (
    domain VARCHAR(255) PRIMARY KEY REFERENCES domain(domain) ON UPDATE CASCADE ON DELETE CASCADE,
    max_sitios INT NOT NULL DEFAULT 1 CHECK (max_sitios >= 0),
    disco_mb INT NOT NULL DEFAULT 2048 CHECK (disco_mb >= 0),
    bases_mb INT NOT NULL DEFAULT 1024 CHECK (bases_mb >= 0),
    actualizado_por VARCHAR(255) NOT NULL DEFAULT '',
    actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
