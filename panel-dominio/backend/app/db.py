import asyncpg

from app import config


async def crear_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        host=config.DB_HOST, port=config.DB_PORT, database=config.DB_NAME,
        user=config.DB_USER, password=config.DB_PASS, min_size=1, max_size=5,
        # La base está en el mismo equipo. Sin esto asyncpg busca certificados de cliente en el
        # directorio personal, que el confinamiento del servicio no deja ver.
        ssl=config.DB_SSL,
    )
