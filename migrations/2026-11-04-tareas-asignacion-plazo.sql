-- Tareas: «Asignar tarea a:» con indicaciones para quien la recibe (30/10/2026).
-- El plazo es la fecha de vencimiento de la tarea (task_cards.due_date); aquí solo se guardan las indicaciones,
-- que son de cada asignación. Idempotente.
ALTER TABLE task_asignados ADD COLUMN IF NOT EXISTS indicaciones TEXT NOT NULL DEFAULT '';
