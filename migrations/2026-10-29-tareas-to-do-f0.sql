-- Tareas al estilo Microsoft To Do, fase F0 (29/10/2026): datos para grupos de listas, listas
-- compartidas, «Mi día» de cada persona, asignación a varias personas y tareas del correo marcado.
-- Solo agrega tablas, columnas e índices: no borra ni cambia nada de lo que hay. Idempotente.
-- Se aplica como el usuario de la aplicación (el de DATABASE_URL).

-- Seguimiento (T-34) crea estas dos piezas al arrancar; aquí también, para que una instalación nueva
-- pueda aplicar esta migración antes del primer arranque. Misma definición: no chocan.
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS asignada BOOLEAN NOT NULL DEFAULT FALSE;
CREATE TABLE IF NOT EXISTS task_asignados (
    card_id     UUID NOT NULL REFERENCES task_cards(id) ON DELETE CASCADE,
    email       TEXT NOT NULL,
    asignado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (card_id, email)
);
CREATE INDEX IF NOT EXISTS idx_task_asignados_email ON task_asignados(email);
-- Quién asignó (en Seguimiento siempre es quien creó la tarea; en una lista compartida, cualquiera).
ALTER TABLE task_asignados ADD COLUMN IF NOT EXISTS asignado_por TEXT NOT NULL DEFAULT '';

-- Grupos de listas de cada persona (sacar una lista del grupo o borrar el grupo no borra la lista).
CREATE TABLE IF NOT EXISTS task_list_groups (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner      TEXT NOT NULL,
    name       TEXT NOT NULL,
    position   INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_task_list_groups_owner ON task_list_groups(owner);

-- Personas de cada lista: la propietaria y, si la comparte, los miembros. El grupo y la posición son
-- de cada persona, porque cada una ordena su barra lateral a su gusto.
CREATE TABLE IF NOT EXISTS task_list_members (
    list_id    UUID NOT NULL REFERENCES task_lists(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    role       TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'member')),
    added_by   TEXT NOT NULL DEFAULT '',
    group_id   UUID REFERENCES task_list_groups(id) ON DELETE SET NULL,
    position   INT NOT NULL DEFAULT 0,
    joined_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (list_id, user_email)
);
CREATE INDEX IF NOT EXISTS idx_task_list_members_user ON task_list_members(user_email);

-- Orden elegido para cada lista: manual, fecha, importancia, alfabético o creación.
ALTER TABLE task_lists ADD COLUMN IF NOT EXISTS sort_by TEXT NOT NULL DEFAULT 'manual';

-- «Mi día» de cada persona y fecha (America/Guayaquil). La vista solo mira la fecha de hoy, así que
-- a medianoche queda vacía sola y la tarea sigue en su lista.
CREATE TABLE IF NOT EXISTS task_mi_dia (
    card_id    UUID NOT NULL REFERENCES task_cards(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    fecha      DATE NOT NULL,
    added_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (card_id, user_email, fecha)
);
CREATE INDEX IF NOT EXISTS idx_task_mi_dia_user_fecha ON task_mi_dia(user_email, fecha);

-- Tarea creada por un correo marcado con bandera: a qué mensaje apunta.
CREATE TABLE IF NOT EXISTS task_correo (
    card_id    UUID PRIMARY KEY REFERENCES task_cards(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    carpeta    TEXT NOT NULL DEFAULT 'INBOX',
    uid        BIGINT NOT NULL,
    message_id TEXT NOT NULL DEFAULT '',
    asunto     TEXT NOT NULL DEFAULT '',
    remitente  TEXT NOT NULL DEFAULT '',
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_task_correo_mensaje
    ON task_correo(user_email, message_id) WHERE message_id <> '';
CREATE INDEX IF NOT EXISTS idx_task_correo_user ON task_correo(user_email, carpeta);

-- Actividad por lista (para las listas compartidas). Sin clave foránea: el registro sobrevive a la lista.
ALTER TABLE task_activity ADD COLUMN IF NOT EXISTS list_id UUID;
CREATE INDEX IF NOT EXISTS idx_task_activity_list ON task_activity(list_id);

-- Datos actuales: cada lista existente pasa a tener a su propietaria (la dueña del tablero).
INSERT INTO task_list_members (list_id, user_email, role, added_by, position)
SELECT tl.id, tb."user", 'owner', tb."user", tl.position
  FROM task_lists tl
  JOIN task_boards tb ON tb.id = tl.board_id
ON CONFLICT DO NOTHING;

-- Las tareas pendientes que hoy están en «Mi día» siguen ahí el día de la migración (para su dueña).
INSERT INTO task_mi_dia (card_id, user_email, fecha)
SELECT tc.id, tb."user", (NOW() AT TIME ZONE 'America/Guayaquil')::date
  FROM task_cards tc
  JOIN task_lists tl ON tl.id = tc.list_id
  JOIN task_boards tb ON tb.id = tl.board_id
 WHERE tc.my_day AND NOT tc.completed
ON CONFLICT DO NOTHING;
