import asyncpg

from app.config import get_settings


async def create_db_pool() -> asyncpg.Pool:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgres://", 1)
    return await asyncpg.create_pool(dsn, min_size=2, max_size=10)
