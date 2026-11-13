-- Vigilante de envío masivo: permisos por lista y seguimiento de cada bloqueo (13/11/2026).
--
-- outbound_anomaly_permisos: esa cuenta puede escribir a esa lista sin que sus miembros cuenten
-- como «envío masivo». No cambia quién puede escribir a la lista (eso es mail_groups.allowed_senders).
-- Se concede desde el panel (Alertas de seguridad) al revisar un bloqueo.
CREATE TABLE IF NOT EXISTS outbound_anomaly_permisos (
    id         BIGSERIAL PRIMARY KEY,
    username   VARCHAR(255) NOT NULL,
    lista      VARCHAR(255) NOT NULL,
    nota       TEXT NOT NULL DEFAULT '',
    creado_por VARCHAR(255) NOT NULL DEFAULT '',
    creado     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (username, lista)
);
-- Cada bloqueo guarda a quién iba el envío (por lista y directos) y qué decidió quien lo revisó.
ALTER TABLE outbound_anomaly_events ADD COLUMN IF NOT EXISTS desglose JSONB;
ALTER TABLE outbound_anomaly_events ADD COLUMN IF NOT EXISTS atendido TIMESTAMPTZ;
ALTER TABLE outbound_anomaly_events ADD COLUMN IF NOT EXISTS atendido_por VARCHAR(255);
ALTER TABLE outbound_anomaly_events ADD COLUMN IF NOT EXISTS resolucion VARCHAR(20);
