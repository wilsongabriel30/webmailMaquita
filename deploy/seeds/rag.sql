CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS rag_chunks (
  id bigserial PRIMARY KEY,
  username varchar NOT NULL,
  folder varchar DEFAULT 'INBOX',
  msg_uid varchar,
  subject text,
  sender text,
  content text,
  embedding vector(768),
  created_at timestamptz DEFAULT now(),
  UNIQUE(username, folder, msg_uid)
);
CREATE INDEX IF NOT EXISTS rag_chunks_user_idx ON rag_chunks (username);
CREATE INDEX IF NOT EXISTS rag_chunks_emb_idx ON rag_chunks USING hnsw (embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS rag_domains (
  domain varchar PRIMARY KEY,
  enabled boolean DEFAULT true,
  created_at timestamptz DEFAULT now()
);
INSERT INTO rag_domains (domain, enabled) VALUES ('maquita.com.ec', true) ON CONFLICT DO NOTHING;
