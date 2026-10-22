-- Enrutamiento de correo por dominio (v1.11): MX de respaldo y reenvío a otro servidor.
-- Las leen los mapas de Postfix (deploy/webmail/configs/postfix-pgsql/pgsql-enrutamiento-*.cf) y
-- las escribe el panel general (Dominios → Enrutamiento). Idempotente.
-- Se aplica como el usuario de la aplicación (el de DATABASE_URL), el mismo que usan los mapas.
--
-- modo «respaldo»: el servidor acepta el correo del dominio y lo encola hasta que su servidor
--                  principal (el MX de menor preferencia) lo reciba.
-- modo «reenvio»:  el correo del dominio se entrega siempre a smtp:[destino_host]:destino_puerto.
-- En los dos, solo se acepta lo que el dominio tiene configurado aquí: con verificar_destinatarios,
-- solo las direcciones de enrutamiento_destinatarios; sin ella, cualquier usuario de ESE dominio
-- (nunca de sus subdominios ni de otros dominios: eso sería un relé abierto).

CREATE TABLE IF NOT EXISTS enrutamiento_correo (
    dominio                 varchar(255) PRIMARY KEY
                            REFERENCES domain (domain) ON DELETE CASCADE ON UPDATE CASCADE,
    modo                    varchar(10)  NOT NULL CHECK (modo IN ('respaldo', 'reenvio')),
    destino_host            varchar(253),
    destino_puerto          integer      CHECK (destino_puerto BETWEEN 1 AND 65535),
    tls_obligatorio         boolean      NOT NULL DEFAULT false,
    verificar_destinatarios boolean      NOT NULL DEFAULT false,
    activo                  boolean      NOT NULL DEFAULT true,
    actualizado_por         varchar(255),
    actualizado_en          timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT enrutamiento_destino_segun_modo CHECK (
        (modo = 'respaldo' AND destino_host IS NULL AND destino_puerto IS NULL)
        OR (modo = 'reenvio' AND destino_host IS NOT NULL AND destino_puerto IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS enrutamiento_destinatarios (
    direccion varchar(320) PRIMARY KEY CHECK (direccion = lower(direccion)),
    dominio   varchar(255) NOT NULL
              REFERENCES enrutamiento_correo (dominio) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT enrutamiento_destinatario_del_dominio CHECK (right(direccion, length(dominio) + 1) = '@' || dominio)
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'idx_enrutamiento_dest_dominio') THEN
        CREATE INDEX idx_enrutamiento_dest_dominio ON enrutamiento_destinatarios (dominio);
    END IF;
    -- El portal de dominio (si está instalado) solo necesita saber si un dominio suyo está enrutado,
    -- para no importar cuentas que no recibirían correo (panel-dominio/deploy/permisos-5-enrutamiento.sql).
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'panel_dominio') THEN
        GRANT SELECT (dominio, activo) ON enrutamiento_correo TO panel_dominio;
    END IF;
END $$;
