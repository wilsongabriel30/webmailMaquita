-- Tareas: un solo tablero «Mi To Do» y una sola lista «Tareas» por persona (29/10/2026).
--
-- Al abrir Tareas por primera vez, las peticiones simultáneas creaban cada una su tablero (ver
-- ensure_default_board): 13 personas quedaron con dos tableros y dos listas «Tareas». Con la misma hora
-- de creación, la tarea nueva podía ir a la lista que la vista no muestra, y «Mover a…» ofrecía «Tareas»
-- dos veces. Se conserva el tablero con más tareas (y listas); lo que hubiera en el otro pasa a él.
-- El actualizador repite todas las migraciones: sin duplicados, esto no cambia nada.

BEGIN;

CREATE TEMP TABLE _tablero_queda ON COMMIT DROP AS
SELECT DISTINCT ON (b."user") b."user", b.id
  FROM task_boards b
 WHERE b.name = 'Mi To Do'
 ORDER BY b."user",
          (SELECT count(*) FROM task_cards c JOIN task_lists l ON l.id = c.list_id WHERE l.board_id = b.id) DESC,
          (SELECT count(*) FROM task_lists l WHERE l.board_id = b.id) DESC,
          b.created_at, b.id;

CREATE TEMP TABLE _tablero_sobra ON COMMIT DROP AS
SELECT b.id AS sobra, q.id AS queda
  FROM task_boards b JOIN _tablero_queda q ON q."user" = b."user"
 WHERE b.name = 'Mi To Do' AND b.id <> q.id;

-- «Tareas» y «Correo electrónico marcado» repetidas: sus tareas pasan a la del tablero que queda.
CREATE TEMP TABLE _lista_sobra ON COMMIT DROP AS
SELECT l.id AS sobra,
       (SELECT k.id FROM task_lists k WHERE k.board_id = s.queda AND k.list_type = l.list_type
         ORDER BY k.position, k.id LIMIT 1) AS queda
  FROM task_lists l JOIN _tablero_sobra s ON s.sobra = l.board_id
 WHERE l.list_type IN ('default', 'flagged');
DELETE FROM _lista_sobra WHERE queda IS NULL;

UPDATE task_cards c SET list_id = x.queda FROM _lista_sobra x WHERE c.list_id = x.sobra;
DELETE FROM task_list_members m USING _lista_sobra x WHERE m.list_id = x.sobra;
DELETE FROM task_lists l USING _lista_sobra x WHERE l.id = x.sobra;

-- Lo demás (listas propias, etiquetas, actividad) se muda entero.
UPDATE task_lists l SET board_id = s.queda FROM _tablero_sobra s WHERE l.board_id = s.sobra;
UPDATE task_labels t SET board_id = s.queda FROM _tablero_sobra s WHERE t.board_id = s.sobra;
UPDATE task_activity a SET board_id = s.queda FROM _tablero_sobra s WHERE a.board_id = s.sobra;
DELETE FROM task_boards b USING _tablero_sobra s WHERE b.id = s.sobra;

COMMIT;

-- Y que no vuelva a pasar en un mismo tablero.
CREATE UNIQUE INDEX IF NOT EXISTS uq_task_lists_una_tareas ON task_lists (board_id) WHERE list_type = 'default';
CREATE UNIQUE INDEX IF NOT EXISTS uq_task_lists_un_marcado ON task_lists (board_id) WHERE list_type = 'flagged';
