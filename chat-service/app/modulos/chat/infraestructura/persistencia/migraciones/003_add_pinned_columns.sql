-- Feature 3: Mensajes Fijados (Pinned Messages)
-- Ejecutar manualmente en PostgreSQL

ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT FALSE;
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS pinned_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS pinned_by INTEGER REFERENCES users(id);

-- Indice parcial para busqueda eficiente de mensajes fijados
CREATE INDEX IF NOT EXISTS idx_chat_messages_pinned
    ON chat_messages(conversation_id, is_pinned) WHERE is_pinned = TRUE;
