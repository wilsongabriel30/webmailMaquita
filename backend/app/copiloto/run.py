"""Runner CLI del Copiloto de Seguridad. Uso: python -m app.copiloto.run "<pregunta>" [dias]"""
import asyncio
import json
import sys

import asyncpg

from app.config import get_settings
from app.copiloto.asistente import ask


async def _main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "falta la pregunta"})); return
    q = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 7
    s = get_settings()
    db = await asyncpg.create_pool(s.database_url, min_size=1, max_size=2)
    try:
        print(json.dumps(await ask(db, q, days=days), ensure_ascii=False, default=str))
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(_main())
