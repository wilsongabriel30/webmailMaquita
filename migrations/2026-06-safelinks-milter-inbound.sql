-- Fase 2 Safe Links: reescritura de enlaces en correos ENTRANTES a nivel milter.
-- Interruptor del panel admin (:8443) para activar/desactivar al instante.
-- Por seguridad arranca APAGADO (false): el equipo lo enciende cuando lo decida.
ALTER TABLE safelinks_config
  ADD COLUMN IF NOT EXISTS milter_inbound_enabled boolean NOT NULL DEFAULT false;
