-- Tareas: fase 3 de la unificación de asignaciones (05/11/2026).
-- Las tareas de lista asignadas con el modelo anterior («Asignar tarea a:» hasta la fase 2) pasan a ser tareas con
-- seguimiento, como las que se asignan ahora: la misma tarea, en su lista, con estado y aceptación.
-- - Quien la asignó (el primero, si fueron varios) queda como quien le da seguimiento (`created_by`).
-- - Completada → estado «completada» y aceptada; si no → «pendiente», sin responder.
-- - Las indicaciones de la asignación pasan a la descripción si esta estaba vacía.
-- Las de «Correo marcado» no se tocan (van ligadas a un buzón). Idempotente: solo toca las que aún no tienen seguimiento.
-- Las columnas de Seguimiento (asignada, estado, aceptación…) las crea la aplicación al arrancar
-- (app/tareas/modelos.py): en una base nueva todavía no existen y no hay nada que pasar, así que no se hace nada.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'task_cards' AND column_name = 'estado') THEN
        RAISE NOTICE 'task_cards sin columnas de Seguimiento: nada que pasar';
        RETURN;
    END IF;

    WITH primera AS (
        SELECT DISTINCT ON (a.card_id) a.card_id, a.asignado_por, a.indicaciones
          FROM task_asignados a
          JOIN task_cards c ON c.id = a.card_id
          JOIN task_lists l ON l.id = c.list_id
         WHERE NOT c.asignada AND l.list_type <> 'flagged'
         ORDER BY a.card_id, a.asignado_en
    )
    UPDATE task_cards c
       SET asignada       = TRUE,
           estado         = CASE WHEN c.completed THEN 'completada' ELSE 'pendiente' END,
           aceptacion     = CASE WHEN c.completed THEN 'aceptada' ELSE 'sin_responder' END,
           motivo_rechazo = '',
           created_by     = COALESCE(NULLIF(p.asignado_por, ''), c.created_by),
           description    = CASE WHEN COALESCE(c.description, '') = ''
                                 THEN COALESCE(NULLIF(c.note, ''), p.indicaciones, '')
                                 ELSE c.description END,
           updated_at     = NOW()
      FROM primera p
     WHERE c.id = p.card_id;
END
$$;
