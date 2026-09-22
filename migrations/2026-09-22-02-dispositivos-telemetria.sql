-- Teléfonos institucionales (22/09/2026): portal de telemetría y alertas automáticas.
-- Telemetría DEL EQUIPO (batería, almacenamiento, red, versiones, eventos de seguridad, acuses):
-- nada de contenido, apps de uso ni navegación. La ubicación no entra aquí (regla de la fase 2).

-- Si la app reporta si sigue siendo administradora del dispositivo, se guarda aquí (NULL = no lo reporta).
ALTER TABLE disp_equipos ADD COLUMN IF NOT EXISTS admin_activo BOOLEAN;

-- Resumen diario por equipo: conserva la tendencia 12 meses sin guardar cada latido (los latidos
-- se borran a los `retencion_latidos_dias`, 30 por omisión). Lo llena el trabajo de alertas.
CREATE TABLE IF NOT EXISTS disp_resumen_diario (
    equipo_id        INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    dia              DATE NOT NULL,
    latidos          INT NOT NULL DEFAULT 0,
    bateria_min      SMALLINT,
    bateria_max      SMALLINT,
    bateria_prom     SMALLINT,
    alm_libre_min    BIGINT,
    alm_libre_prom   BIGINT,
    alm_total        BIGINT,
    version_app      VARCHAR(40),
    android          VARCHAR(40),
    latidos_wifi     INT NOT NULL DEFAULT 0,
    latidos_movil    INT NOT NULL DEFAULT 0,
    actualizado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (equipo_id, dia)
);

-- Alertas: una fila por condición abierta (hasta IS NULL) para no repetir el mismo aviso; se cierra
-- sola cuando la condición desaparece. Se muestran en el portal y se avisan por correo.
CREATE TABLE IF NOT EXISTS disp_alertas (
    id          SERIAL PRIMARY KEY,
    equipo_id   INT NOT NULL REFERENCES disp_equipos(id) ON DELETE CASCADE,
    tipo        VARCHAR(32) NOT NULL,
    detalle     JSONB NOT NULL DEFAULT '{}'::jsonb,
    desde       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hasta       TIMESTAMPTZ,
    avisada_en  TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS disp_alertas_abierta ON disp_alertas (equipo_id, tipo) WHERE hasta IS NULL;
CREATE INDEX IF NOT EXISTS disp_alertas_desde ON disp_alertas (desde DESC);

-- Umbrales editables desde el panel (no en código). El correo de Tecnología recibe cada alerta nueva;
-- «resumen_diario_para» (correos separados por coma) recibe un resumen a la hora indicada.
INSERT INTO disp_config (clave, valor) VALUES
  ('alertas', '{"activo": true, "sin_reportar_horas": 24, "bateria_pct": 15, "bateria_horas": 6, "almacenamiento_pct": 10, "version_atrasada_dias": 7, "acuse_horas": 2, "correo_ti": "gestiontecnologia@maquita.org", "resumen_diario_para": "", "resumen_hora": "07:30"}')
ON CONFLICT (clave) DO NOTHING;
