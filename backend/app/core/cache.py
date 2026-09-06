"""Generic cache repository — encapsulates Redis get/set/invalidate with TTL."""

import json
from typing import Any


class CacheRepository:
    """Typed cache access over Redis."""

    def __init__(self, redis, prefix: str, default_ttl: int = 60):
        self._redis = redis
        self._prefix = prefix
        self._default_ttl = default_ttl

    def _key(self, key: str) -> str:
        return f"cache:{self._prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(self._key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = ttl or self._default_ttl
        if isinstance(value, (dict, list)):
            raw = json.dumps(value, default=str)
        else:
            raw = str(value)
        await self._redis.set(self._key(key), raw, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._redis.delete(self._key(key))

    async def invalidate_prefix(self, pattern: str) -> None:
        """Delete all keys matching a pattern under this cache prefix."""
        full_pattern = self._key(pattern + "*")
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(cursor, match=full_pattern, count=100)
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break
