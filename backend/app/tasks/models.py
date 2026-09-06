"""Task board tables — PostgreSQL DDL (Microsoft To Do style)."""
from __future__ import annotations

import asyncpg

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS task_boards (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "user"      TEXT NOT NULL,
    name        TEXT NOT NULL,
    color       TEXT NOT NULL DEFAULT '#0078d4',
    position    INT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_board_members (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id    UUID NOT NULL REFERENCES task_boards(id) ON DELETE CASCADE,
    user_email  TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    invited_by  TEXT NOT NULL,
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(board_id, user_email)
);

CREATE TABLE IF NOT EXISTS task_lists (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id    UUID NOT NULL REFERENCES task_boards(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    position    INT NOT NULL DEFAULT 0,
    color       TEXT NOT NULL DEFAULT '#e0e0e0',
    list_type   TEXT NOT NULL DEFAULT 'custom',
    icon        TEXT NOT NULL DEFAULT '',
    owner       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS task_cards (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id       UUID NOT NULL REFERENCES task_lists(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    due_date      TIMESTAMPTZ,
    priority      TEXT NOT NULL DEFAULT 'medium'
                  CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    labels        JSONB NOT NULL DEFAULT '[]'::jsonb,
    completed     BOOLEAN NOT NULL DEFAULT FALSE,
    position      INT NOT NULL DEFAULT 0,
    assigned_to   TEXT,
    created_by    TEXT NOT NULL DEFAULT '',
    completed_by  TEXT,
    completed_at  TIMESTAMPTZ,
    important     BOOLEAN NOT NULL DEFAULT FALSE,
    my_day        BOOLEAN NOT NULL DEFAULT FALSE,
    reminder      TIMESTAMPTZ,
    note          TEXT NOT NULL DEFAULT '',
    recurrence    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_labels (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id    UUID NOT NULL REFERENCES task_boards(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    color       TEXT NOT NULL DEFAULT '#0078d4'
);

CREATE TABLE IF NOT EXISTS task_activity (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id    UUID NOT NULL REFERENCES task_boards(id) ON DELETE CASCADE,
    card_id     UUID REFERENCES task_cards(id) ON DELETE SET NULL,
    user_email  TEXT NOT NULL,
    action      TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_boards_user ON task_boards("user");
CREATE INDEX IF NOT EXISTS idx_task_board_members_board ON task_board_members(board_id);
CREATE INDEX IF NOT EXISTS idx_task_board_members_user ON task_board_members(user_email);
CREATE INDEX IF NOT EXISTS idx_task_lists_board ON task_lists(board_id);
CREATE INDEX IF NOT EXISTS idx_task_cards_list ON task_cards(list_id);
CREATE INDEX IF NOT EXISTS idx_task_labels_board ON task_labels(board_id);
CREATE INDEX IF NOT EXISTS idx_task_activity_board ON task_activity(board_id);
CREATE INDEX IF NOT EXISTS idx_task_activity_card ON task_activity(card_id);
""";

MIGRATE_SQL = """
DO $$ BEGIN
    ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS assigned_to TEXT;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS created_by TEXT NOT NULL DEFAULT '';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS completed_by TEXT;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS important BOOLEAN NOT NULL DEFAULT FALSE;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS my_day BOOLEAN NOT NULL DEFAULT FALSE;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS reminder TIMESTAMPTZ;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS note TEXT NOT NULL DEFAULT '';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS recurrence TEXT;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE task_lists ADD COLUMN IF NOT EXISTS list_type TEXT NOT NULL DEFAULT 'custom';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE task_lists ADD COLUMN IF NOT EXISTS icon TEXT NOT NULL DEFAULT '';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE task_lists ADD COLUMN IF NOT EXISTS owner TEXT NOT NULL DEFAULT '';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS task_board_members (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id    UUID NOT NULL REFERENCES task_boards(id) ON DELETE CASCADE,
    user_email  TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    invited_by  TEXT NOT NULL,
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(board_id, user_email)
);

CREATE TABLE IF NOT EXISTS task_activity (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id    UUID NOT NULL REFERENCES task_boards(id) ON DELETE CASCADE,
    card_id     UUID REFERENCES task_cards(id) ON DELETE SET NULL,
    user_email  TEXT NOT NULL,
    action      TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
""";

POST_MIGRATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_task_cards_assigned ON task_cards(assigned_to);
CREATE INDEX IF NOT EXISTS idx_task_cards_important ON task_cards(important);
CREATE INDEX IF NOT EXISTS idx_task_cards_my_day ON task_cards(my_day);
CREATE INDEX IF NOT EXISTS idx_task_cards_due_date ON task_cards(due_date);
CREATE INDEX IF NOT EXISTS idx_task_board_members_board ON task_board_members(board_id);
CREATE INDEX IF NOT EXISTS idx_task_board_members_user ON task_board_members(user_email);
CREATE INDEX IF NOT EXISTS idx_task_activity_board ON task_activity(board_id);
CREATE INDEX IF NOT EXISTS idx_task_activity_card ON task_activity(card_id);
""";


async def ensure_tables(pool: asyncpg.Pool) -> None:
    """Create task tables if they don't exist, and run migrations."""
    await pool.execute(CREATE_TABLES_SQL)
    await pool.execute(MIGRATE_SQL)
    await pool.execute(POST_MIGRATE_INDEXES_SQL)

# Subtasks / checklist steps
CREATE_SUBTASKS_SQL = """
CREATE TABLE IF NOT EXISTS task_steps (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id     UUID NOT NULL REFERENCES task_cards(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    completed   BOOLEAN NOT NULL DEFAULT FALSE,
    position    INT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_task_steps_card ON task_steps(card_id);
"""
