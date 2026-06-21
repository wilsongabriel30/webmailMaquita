"""Runner CLI/cron de agentes. Uso: python -m app.agents.run <agente> [--apply]"""
import asyncio
import json
import sys

import asyncpg

from app.config import get_settings
from app.agents.runner import run_agent, list_agents


class _NoRedis:
    async def delete(self, *a):
        pass

    async def set(self, *a, **k):
        pass


async def _main():
    if len(sys.argv) < 2:
        print("agentes:", ", ".join(a["name"] for a in list_agents()))
        return
    name = sys.argv[1]
    dry = "--apply" not in sys.argv[2:]
    s = get_settings()
    db = await asyncpg.create_pool(s.database_url, min_size=1, max_size=2)
    try:
        res = await run_agent(name, db, _NoRedis(), s, dry_run=dry)
        print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(_main())
