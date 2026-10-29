-- Tareas al estilo To Do, F6 (29/10/2026): configuración personal de Tareas (la ⚙ de la barra).
-- Se guarda en el servidor para que siga a la persona en cualquier equipo. Las claves que falten toman su valor
-- por defecto (app/tasks/ajustes.py), así que agregar una opción nueva no necesita migración.
ALTER TABLE task_preferencias ADD COLUMN IF NOT EXISTS ajustes JSONB NOT NULL DEFAULT '{}'::jsonb;
