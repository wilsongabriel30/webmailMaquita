import redis.asyncio as aioredis

from app.config import get_settings
from app.escala.redis_conexion import crear_cliente, leer_config


async def create_redis() -> aioredis.Redis:
    """Cliente Redis del servicio: redis:// simple (de serie) o Sentinel si se configura."""
    return crear_cliente(leer_config(get_settings()))
