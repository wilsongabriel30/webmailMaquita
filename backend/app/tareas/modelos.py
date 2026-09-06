"""DDL de T-34 (idempotente). Se ejecuta en el arranque, bajo el mismo candado que las tablas de tareas."""

import asyncpg

DDL = """
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS asignada        BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS estado          TEXT NOT NULL DEFAULT 'pendiente';
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS aceptacion      TEXT NOT NULL DEFAULT 'sin_responder';
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS motivo_rechazo  TEXT NOT NULL DEFAULT '';
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS correo_ref      JSONB;
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS activa_tarea_id UUID;
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS escalar_a       TEXT;
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS escalado_en     TIMESTAMPTZ;
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS aviso_24h_en    TIMESTAMPTZ;
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS aviso_vencida_en TIMESTAMPTZ;
ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS etiquetas       JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS task_asignados (
    card_id     UUID NOT NULL REFERENCES task_cards(id) ON DELETE CASCADE,
    email       TEXT NOT NULL,
    asignado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (card_id, email)
);
CREATE INDEX IF NOT EXISTS idx_task_asignados_email ON task_asignados(email);

CREATE TABLE IF NOT EXISTS task_comentarios (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id     UUID NOT NULL REFERENCES task_cards(id) ON DELETE CASCADE,
    autor       TEXT NOT NULL,
    texto       TEXT NOT NULL,
    menciones   JSONB NOT NULL DEFAULT '[]'::jsonb,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_task_comentarios_card ON task_comentarios(card_id);

CREATE TABLE IF NOT EXISTS task_escalamiento (
    departamento TEXT PRIMARY KEY,
    jefe_email   TEXT NOT NULL,
    dias         INT NOT NULL DEFAULT 2,
    actualizado_por TEXT NOT NULL DEFAULT '',
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_avisos (
    id        BIGSERIAL PRIMARY KEY,
    card_id   UUID REFERENCES task_cards(id) ON DELETE CASCADE,
    tipo      TEXT NOT NULL,
    a         TEXT NOT NULL,
    texto     TEXT NOT NULL DEFAULT '',
    enviado   BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_task_cards_asignada ON task_cards(asignada) WHERE asignada;
"""


async def asegurar_tablas(pool: asyncpg.Pool) -> None:
    await pool.execute(DDL)
