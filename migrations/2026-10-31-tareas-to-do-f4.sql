-- Tareas al estilo Microsoft To Do, fase F4 (30/10/2026): compartir listas y asignar tareas.
-- Las personas de cada lista (task_list_members), los asignados (task_asignados) y la actividad (task_activity.list_id)
-- ya existen desde la F0. Aquí solo se agrega la preferencia de cada persona de recibir los avisos también por correo.
-- Solo agrega una tabla: no borra ni cambia nada de lo que hay. Idempotente. Se aplica como el usuario de la aplicación.

CREATE TABLE IF NOT EXISTS task_preferencias (
    user_email    TEXT PRIMARY KEY,
    avisos_correo BOOLEAN NOT NULL DEFAULT FALSE,
    cambiado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
