"""Proxy — canonical source is app.redis_client (Fase 2 cleanup)."""
from app.redis_client import *  # noqa: F401,F403
from app.redis_client import create_redis  # explicit re-export
