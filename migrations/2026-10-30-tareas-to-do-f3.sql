-- Tareas al estilo Microsoft To Do, fase F3 (30/10/2026): archivos adjuntos de las tareas.
-- Solo agrega una tabla y su índice: no borra ni cambia nada de lo que hay. Idempotente.
-- Se aplica como el usuario de la aplicación (el de DATABASE_URL).
-- Los archivos van en disco (TAREAS_ADJUNTOS_DIR, por defecto /var/lib/maquita-webmail/task-attachments);
-- aquí queda el nombre original, el tipo, el tamaño y quién lo subió.
-- La repetición personalizada no necesita tabla: la regla va en task_cards.recurrence (ver app/tasks/repeticion.py).

CREATE TABLE IF NOT EXISTS task_adjuntos (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id      UUID NOT NULL REFERENCES task_cards(id) ON DELETE CASCADE,
    nombre       TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    tamano       BIGINT NOT NULL,
    archivo      TEXT NOT NULL,
    subido_por   TEXT NOT NULL,
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_task_adjuntos_card ON task_adjuntos(card_id);
