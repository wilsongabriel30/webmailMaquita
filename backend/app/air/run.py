"""Runner del AIR para cron/CLI (detect-only). Uso: python -m app.air.run [horas]

Corre un ciclo de investigación: correlaciona señales, hace triage con la IA,
registra los incidentes en threat_actions y los imprime. NO contiene cuentas
(la contención automática solo ocurre vía la API con auto_respond y config).
"""
import asyncio
import sys

import asyncpg

from app.config import get_settings
from app.air.engine import run_cycle


class _NoRedis:                     # detect-only no toca Redis
    async def delete(self, *a):
        pass

    async def set(self, *a, **k):
        pass


async def _main():
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    s = get_settings()
    db = await asyncpg.create_pool(s.database_url, min_size=1, max_size=2)
    try:
        inc = await run_cycle(db, _NoRedis(), hours=hours, use_ai=True, auto_respond=False)
        print(f"AIR: {len(inc)} incidente(s) en las últimas {hours}h")
        for i in inc:
            ai = i.get("ai") or {}
            print(f"  {i['username']}  [{i['severity']} -> {i['action']}]  score={i['signals']['score']}")
            if i["reasons"]:
                print(f"    señales: {'; '.join(i['reasons'])}")
            if ai:
                print(f"    IA: {ai.get('recomendacion', '')} ({ai.get('confianza', 0)}%) — {ai.get('resumen', '')}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(_main())
