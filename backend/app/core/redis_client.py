import redis.asyncio as aioredis
from app.config import get_settings


async def create_redis() -> aioredis.Redis:
    settings = get_settings()
    return aioredis.from_url(settings.redis_url, decode_responses=True)
