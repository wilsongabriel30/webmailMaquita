-- La tabla `security_config` no la creaba ninguna migración: existía solo donde alguien la había
-- hecho a mano. Lo detectó el equipo replica (Andes) el 09/09/2026 en dos sitios a la vez:
--
--   * en su producción, el milter la consulta cada ~20 segundos y caía al fail-safe con
--     UndefinedTableError EN BUCLE (638 entradas en el journal desde el día 7, empezando en el
--     minuto exacto en que rodaron v1.7.9);
--   * y en una instalación desde cero de v1.7.16 en una VM desechable, donde tampoco existía y
--     el milter registró el mismo error.
--
-- El fail-safe salva el correo —por eso nadie lo notaba—, pero la pantalla de políticas del panel
-- no puede funcionar (la lee con WHERE id = 1) y el journal se llena de errores que tapan avisos
-- de verdad.
--
-- Idempotente: se puede aplicar sobre una instalación que ya la tenga (la nuestra) sin tocar sus
-- valores.

CREATE TABLE IF NOT EXISTS security_config (
    -- Fila única: la configuración de seguridad es una, y el código la lee con WHERE id = 1.
    id                       integer     PRIMARY KEY DEFAULT 1,
    -- Suplantación desde el panel: activada, y sobre qué términos de correo se permite.
    impersonation_enabled    boolean     DEFAULT true,
    impersonation_terms      text[]      DEFAULT ARRAY['maquita', 'mcch', 'cushunchic'],
    -- Protección de datos: bloquear tarjetas hacia destinatarios externos.
    dlp_block_cards_external boolean     DEFAULT true,
    updated_at               timestamptz DEFAULT now(),
    -- Segundo factor obligatorio y hasta cuándo hay de plazo.
    totp_required            boolean     NOT NULL DEFAULT false,
    totp_deadline            date
);

-- La fila que el código espera encontrar. Sin ella, leer la configuración devuelve vacío y cada
-- consulta acaba en el fail-safe, que es justo lo que se quiere evitar.
INSERT INTO security_config (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

-- Una sola fila, siempre: si alguien intenta añadir otra, que falle aquí y no en la aplicación.
ALTER TABLE security_config DROP CONSTRAINT IF EXISTS security_config_fila_unica;
ALTER TABLE security_config ADD CONSTRAINT security_config_fila_unica CHECK (id = 1);
