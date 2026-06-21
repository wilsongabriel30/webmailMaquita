"""Ingesta RAG incremental. Uso: python -m app.rag.run [--user correo]"""
import asyncio
import json
import sys

import asyncpg

from app.config import get_settings
from app.rag.ingest import ingest_user


async def _main():
    s = get_settings()
    db = await asyncpg.create_pool(s.database_url, min_size=1, max_size=3)
    try:
        if "--ask" in sys.argv and "--user" in sys.argv:
            u = sys.argv[sys.argv.index("--user") + 1]
            q = sys.argv[sys.argv.index("--ask") + 1]
            from app.rag.ask import ask
            print(json.dumps(await ask(db, u, q), ensure_ascii=False)); return
        if "--user" in sys.argv and sys.argv.index("--user") + 1 < len(sys.argv):
            u = sys.argv[sys.argv.index("--user") + 1]
            print(json.dumps(await ingest_user(db, u), ensure_ascii=False)); return
        doms = [r["domain"] for r in await db.fetch("SELECT domain FROM rag_domains WHERE enabled=true")]
        if not doms:
            print("sin dominios RAG habilitados"); return
        users = [r["username"] for r in await db.fetch(
            "SELECT username FROM mailbox WHERE active=true AND split_part(username,'@',2)=ANY($1::text[])", doms)]
        tot = 0
        for u in users:
            r = await ingest_user(db, u)
            tot += r.get("indexed", 0)
        print(f"ingesta RAG: {len(users)} buzones, {tot} correos nuevos")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(_main())
