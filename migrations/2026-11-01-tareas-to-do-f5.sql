-- Tareas al estilo To Do, F5 (31/10/2026): aviso del día de vencimiento.
-- vence_avisado = fecha (Guayaquil) en que se avisó «Vence hoy»; el programador de recordatorios lo reclama de forma
-- atómica, así que cada tarea se avisa una sola vez por fecha aunque haya varios procesos.
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS vence_avisado DATE;
