-- Alertas de seguridad: mensajes enviados a la persona de una alerta (13/11/2026).
--
-- El botón «Enviar mensaje» del panel escribe a la cuenta que tiene intentos fallidos repetidos
-- desde un celular u otro programa de correo (contraseña vieja guardada). Aquí queda quién lo
-- envió, a quién, cuándo y el texto; la alerta muestra el último envío y, si fue hace menos de
-- 24 horas, el panel pide confirmación antes de enviar otro.
-- Idempotente. Se aplica como el usuario de la aplicación (el de DATABASE_URL).
CREATE TABLE IF NOT EXISTS alertas_mensajes_persona (
    id          BIGSERIAL PRIMARY KEY,
    cuenta      VARCHAR(255) NOT NULL,
    asunto      TEXT NOT NULL,
    cuerpo      TEXT NOT NULL,
    remitente   VARCHAR(255) NOT NULL DEFAULT '',
    enviado_por VARCHAR(255) NOT NULL,
    enviado     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_alertas_mensajes_persona_cuenta ON alertas_mensajes_persona (cuenta, enviado DESC);
