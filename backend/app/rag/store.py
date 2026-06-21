"""Almacén pgvector de fragmentos de correo para RAG."""


async def ensure_schema(db):
    await db.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await db.execute(
        "CREATE TABLE IF NOT EXISTS rag_chunks (id bigserial PRIMARY KEY, username varchar NOT NULL, "
        "folder varchar DEFAULT 'INBOX', msg_uid varchar, subject text, sender text, content text, "
        "embedding vector(768), created_at timestamptz DEFAULT now(), UNIQUE(username, folder, msg_uid))")


async def existing_uids(db, username, folder="INBOX"):
    rows = await db.fetch("SELECT msg_uid FROM rag_chunks WHERE username=$1 AND folder=$2", username, folder)
    return {r["msg_uid"] for r in rows}


async def upsert(db, username, folder, uid, subject, sender, content, embedding):
    await db.execute(
        "INSERT INTO rag_chunks (username,folder,msg_uid,subject,sender,content,embedding) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7::vector) ON CONFLICT (username,folder,msg_uid) DO NOTHING",
        username, folder, str(uid), subject, sender, content, str(embedding))


async def search(db, username, query_emb, k=6):
    return await db.fetch(
        "SELECT subject, sender, content, 1-(embedding <=> $1::vector) sim FROM rag_chunks "
        "WHERE username=$2 ORDER BY embedding <=> $1::vector LIMIT $3", str(query_emb), username, k)


async def count(db, username):
    return await db.fetchval("SELECT count(*) FROM rag_chunks WHERE username=$1", username) or 0
