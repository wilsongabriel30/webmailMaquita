-- Etiquetas: asignaciones cuyo correo IMAP ya no devuelve (09/11/2026). Idempotente.
-- `faltante_desde` NULL = vigente (cuenta y se lista). Con fecha = IMAP no devolvió el correo al listar la
-- etiqueta; no cuenta ni se lista, se limpia si el correo reaparece y se borra pasados 7 días
-- (backend/app/mail/services/etiquetas_huerfanas.py).
ALTER TABLE message_labels ADD COLUMN IF NOT EXISTS faltante_desde TIMESTAMPTZ NULL;

-- Contador lateral y total del listado: solo vigentes.
CREATE INDEX IF NOT EXISTS idx_mlabels_vigentes
    ON message_labels (owner, label_id) WHERE faltante_desde IS NULL;

-- Purga diaria de faltantes antiguas.
CREATE INDEX IF NOT EXISTS idx_mlabels_faltantes
    ON message_labels (faltante_desde) WHERE faltante_desde IS NOT NULL;
